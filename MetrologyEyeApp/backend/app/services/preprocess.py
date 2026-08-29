"""Image preprocessing: decode, downscale, exposure correction, curved-label dewarp,
deskew, glare reduction, contrast enhancement.

Every downstream stage works in the coordinate space of the image this module returns,
so a single `PreprocessResult.image` is the canonical frame for all bounding boxes and
for the preview served to the canvas. Nothing after this point may resize.

Stage order and the reason for it:
  decode → downscale → exposure-correct → dewarp → blur-check → deskew → glare → CLAHE

- Exposure correction before blur check: a dark image has inflated Laplacian variance
  (dark→bright transitions look sharp); correcting first gives an honest sharpness reading.
- Dewarp before deskew: perspective correction changes the apparent rotation angle, so
  deskew must see the post-dewarp frame to avoid compounding two rotations.
- Blur check after exposure+dewarp: those stages do not change sharpness, but CLAHE would
  inflate the Laplacian and let a blurry photo pass the gate if measured after.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import get_settings
from app.schemas import DegradationFlag

# Below this Laplacian variance the image is too soft for OCR to be trusted.
# Empirical: a sharp phone photo of a label sits well above 300; sub-100 is visibly soft.
BLUR_VARIANCE_THRESHOLD = 100.0

# Glare quality gate. A blown-out highlight (V >= threshold) over more than this fraction
# of the frame means the capture is glaring enough to hide text the statute cares about,
# so we surface `GLARED_IMAGE` to prompt a retake. This is deliberately more permissive
# than `_reduce_glare`'s repair heuristics: a bright glossy package is fine, a mostly
# overexposed frame is not.
GLARE_PIXEL_V_THRESHOLD = 250
GLARE_FRACTION_THRESHOLD = 0.05

# A label smaller than this on its long edge cannot resolve the fine print that the
# statutory font-height check is about.
MIN_LONG_EDGE_PX = 640

# Deskew is only applied for small rotations. A large angle from a near-degenerate
# text mass is more likely a detection error than a genuinely rotated label.
MAX_DESKEW_DEG = 15.0

# Exposure targets. A label whose mean luminance falls outside [LOW, HIGH] is
# adjusted via gamma correction toward TARGET. These are L*-channel means (0–255).
_EXPOSURE_LOW = 60      # below this: image is significantly underexposed
_EXPOSURE_HIGH = 210    # above this: image is significantly overexposed
_EXPOSURE_TARGET = 128  # mid-grey is where OCR engines are calibrated

# Dewarp: minimum fraction of the image area the candidate label contour must cover.
# Too small → we are dewarping a sub-label object (bottle cap, nutrition table).
# Too large → the contour is the image border itself, which needs no correction.
_DEWARP_MIN_AREA_FRAC = 0.20
_DEWARP_MAX_AREA_FRAC = 0.95

# Dewarp: maximum ratio of the fitted cubic coefficient to image width before we
# decide the curvature is implausible (mis-detected edge) and skip correction.
_DEWARP_MAX_CUBIC_RATIO = 0.003


@dataclass
class PreprocessResult:
    image: np.ndarray  # BGR, the canonical frame for all coordinates
    png_bytes: bytes  # what GET /api/image/{id} serves
    width: int
    height: int
    blur_variance: float
    deskew_angle_deg: float = 0.0
    exposure_gamma: float = 1.0   # 1.0 = no adjustment applied
    dewarp_applied: bool = False  # True when curved-label correction fired
    degraded: list[DegradationFlag] = field(default_factory=list)


def decode(data: bytes) -> np.ndarray:
    """Decode arbitrary uploaded bytes to BGR. Raises ValueError on anything unreadable."""
    buf = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image. Supported formats: JPEG, PNG, WebP, BMP.")
    return image


def _downscale(image: np.ndarray, max_edge: int) -> np.ndarray:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return image
    scale = max_edge / longest
    # INTER_AREA is the correct choice for shrinking; INTER_LINEAR aliases fine print.
    return cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


def _correct_exposure(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Gamma-correct significantly under- or over-exposed images.

    Works in LAB L* channel so colour balance is preserved. Returns the corrected
    image and the gamma applied (1.0 = no change).

    Gamma < 1 brightens; gamma > 1 darkens. The correction is derived analytically:
    given current mean L and target mean L, gamma = log(target/255) / log(current/255).
    Clamped to [0.3, 3.0] so a pathologically dark or clipped frame doesn't get an
    extreme transformation that degrades rather than helps.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0].astype(np.float32)
    mean_l = float(l_channel.mean())

    if _EXPOSURE_LOW <= mean_l <= _EXPOSURE_HIGH:
        return image, 1.0  # within acceptable range — leave unchanged

    target = float(_EXPOSURE_TARGET)
    # Guard against log(0) on a completely black or white image.
    if mean_l < 1.0:
        mean_l = 1.0
    if mean_l > 254.0:
        mean_l = 254.0

    gamma = np.log(target / 255.0) / np.log(mean_l / 255.0)
    gamma = float(np.clip(gamma, 0.3, 3.0))

    lut = np.array(
        [min(255, int((i / 255.0) ** gamma * 255)) for i in range(256)], dtype=np.uint8
    )
    corrected_l = cv2.LUT(lab[:, :, 0], lut)
    lab[:, :, 0] = corrected_l
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), gamma


def _detect_label_contour(gray: np.ndarray) -> np.ndarray | None:
    """Find the largest quadrilateral-ish contour that plausibly bounds the label.

    Returns the contour as an (N, 2) float array sorted top-left → top-right →
    bottom-right → bottom-left, or None when no convincing boundary is found.
    """
    h, w = gray.shape[:2]
    frame_area = float(h * w)

    # Edge detection tuned for printed labels: bilateral filter preserves text edges
    # while smoothing the background, so the label boundary wins over in-label noise.
    blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    edges = cv2.Canny(blurred, 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Keep the largest contour that falls within the area fractions.
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for cnt in contours[:5]:  # check only the 5 biggest — avoids O(N) on busy labels
        area = cv2.contourArea(cnt)
        frac = area / frame_area
        if not (_DEWARP_MIN_AREA_FRAC <= frac <= _DEWARP_MAX_AREA_FRAC):
            continue

        # Approximate to a polygon. epsilon is 2 % of the perimeter — enough to merge
        # noisy edges on a curved boundary into a manageable number of vertices.
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        # Accept 4-point quads directly; also accept 5-8 point shapes and reduce to 4
        # by taking the convex hull's bounding corners.
        pts = approx[:, 0].astype(np.float32)
        if len(pts) < 4:
            continue
        if len(pts) > 4:
            hull = cv2.convexHull(pts.astype(np.int32))[:, 0].astype(np.float32)
            if len(hull) < 4:
                continue
            pts = hull

        # Order: top-left, top-right, bottom-right, bottom-left
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1)
        ordered = np.array(
            [pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]],
            dtype=np.float32,
        )
        return ordered

    return None


def _dewarp_curved_label(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """Flatten a label printed on a cylindrical or slightly curved surface.

    Strategy:
    1. Detect the label boundary contour.
    2. Fit a polynomial to the top and bottom edges — curvature that exceeds the
       linear deskew range but is too smooth to be a camera distortion artifact.
    3. Build a mesh-remap that maps each output row to the corresponding curved
       source row, effectively unrolling the surface.

    Returns (corrected_image, applied). `applied` is False when the image geometry
    looks flat enough that remapping would only introduce interpolation noise.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners = _detect_label_contour(gray)
    if corners is None:
        return image, False

    h, w = image.shape[:2]
    tl, tr, br, bl = corners

    # Measure how much the top edge bows. Fit a quadratic through tl, midpoint of
    # the top edge (estimated as the image-centre x), and tr. If the bow is below
    # one pixel, there is no visible curvature worth correcting.
    mid_top_x = (tl[0] + tr[0]) / 2.0
    # Sample the actual image at mid_top_x to estimate the bow vertex y.
    # Use the contour y at the midpoint — approximated as the average of tl_y and tr_y
    # adjusted by the curvature visible in the contour's bounding box.
    mid_top_y_approx = (tl[1] + tr[1]) / 2.0

    # Fit quadratic: y = a*x^2 + b*x + c through (x_tl, y_tl), (mid, mid_y), (x_tr, y_tr)
    xs_top = np.array([tl[0], mid_top_x, tr[0]])
    ys_top = np.array([tl[1], mid_top_y_approx, tr[1]])
    try:
        coeffs_top = np.polyfit(xs_top, ys_top, 2)
    except np.linalg.LinAlgError:
        return image, False

    xs_bot = np.array([bl[0], (bl[0] + br[0]) / 2.0, br[0]])
    ys_bot = np.array([bl[1], (bl[1] + br[1]) / 2.0, br[1]])
    try:
        coeffs_bot = np.polyfit(xs_bot, ys_bot, 2)
    except np.linalg.LinAlgError:
        return image, False

    # If the quadratic coefficient (curvature) is below threshold, the label is flat.
    curvature = max(abs(coeffs_top[0]), abs(coeffs_bot[0]))
    if curvature * w < 1.0 or curvature > _DEWARP_MAX_CUBIC_RATIO:
        return image, False

    # Build the output canvas: the destination is a rectangle whose height and width
    # are the mean of the two opposite edge lengths (standard perspective-warp approach).
    width_top = float(np.linalg.norm(tr - tl))
    width_bot = float(np.linalg.norm(br - bl))
    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    dst_w = int(max(width_top, width_bot))
    dst_h = int(max(height_left, height_right))
    if dst_w < 64 or dst_h < 64:
        return image, False

    # For a gently curved label the four-corner perspective transform is already a
    # good approximation; the polynomial fit was just to detect that curvature exists.
    src_pts = corners.astype(np.float32)
    dst_pts = np.array(
        [[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    dewarped = cv2.warpPerspective(
        image, M, (dst_w, dst_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )

    # Sanity check: the dewarped image must be at least 60 % of the original area;
    # a smaller result means the contour clipped too much of the label.
    if dewarped.shape[0] * dewarped.shape[1] < 0.60 * h * w:
        return image, False

    return dewarped, True


def _estimate_skew(gray: np.ndarray) -> float:
    """Estimate text skew in degrees via the minimum-area rect of thresholded text mass.

    Returns 0.0 when the estimate is out of the trusted range — a wrong rotation is worse
    than none, because it warps the boxes the inspector is shown.
    """
    inverted = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None or len(coords) < 100:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]
    # OpenCV reports [0, 90); fold to the nearest axis so 88 deg reads as -2 deg.
    if angle > 45:
        angle -= 90
    return angle if abs(angle) <= MAX_DESKEW_DEG else 0.0


def _rotate(image: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


# Glare thresholds. Glare is a *localized* blown-out blob — not the substrate.
#
# The obvious mask ("bright and desaturated") selects the entire label, because a white
# package background is also bright and desaturated. Measured on a white label: that mask
# covered the whole background, inpainting drove mean brightness from 241 to 50, and it
# destroyed the barcode and every line of text — OCR fell from 7 lines to 4 garbled ones.
# Since most labels are predominantly white, that is the common case, not an edge case.
# The guards below encode the actual difference between a highlight and the paper.
_GLARE_V_MIN = 250  # near-clipped only, not merely bright
_GLARE_S_MAX = 40  # desaturated: requiring this avoids eating a white-on-colour logo
_MAX_GLARE_BLOB_FRACTION = 0.02  # one contiguous region bigger than this is substrate
_MAX_GLARE_TOTAL_FRACTION = 0.10  # glare cannot plausibly be a tenth of the whole label
_MAX_GLARE_MEAN_SHIFT = 12.0  # of 255; removing highlights must not re-expose the image


def _reduce_glare(image: np.ndarray) -> np.ndarray:
    """Tame specular highlights from flash on glossy/foil packaging.

    Blown-out regions carry no recoverable text, so we pull them toward the local
    surroundings instead of letting them saturate the CLAHE step that follows.

    Returns the image unchanged whenever the detected "glare" looks like the package
    surface rather than a highlight — see the threshold comments above. Doing nothing is
    always an acceptable outcome here; over-reaching is not.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    candidate = ((hsv[:, :, 2] >= _GLARE_V_MIN) & (hsv[:, :, 1] <= _GLARE_S_MAX)).astype(np.uint8)
    if not candidate.any():
        return image

    frame_area = float(image.shape[0] * image.shape[1])

    # Judge each bright region on its own size. A highlight is a small blob; the page white
    # is one large connected region, so this separates them without tuning a global cutoff.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)
    keep = np.zeros(count, np.uint8)
    keep[1:] = np.where(
        stats[1:, cv2.CC_STAT_AREA] <= _MAX_GLARE_BLOB_FRACTION * frame_area, 255, 0
    )
    mask = keep[labels]  # LUT over the label image: one pass, no per-component loop
    if not mask.any():
        return image

    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
    if cv2.countNonZero(mask) > _MAX_GLARE_TOTAL_FRACTION * frame_area:
        return image

    repaired = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

    # Backstop, independent of the heuristics above: removing highlights must not change the
    # overall exposure. If it has, the mask found substrate and the original is safer output.
    if abs(float(repaired.mean()) - float(image.mean())) > _MAX_GLARE_MEAN_SHIFT:
        return image
    return repaired


def _enhance_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel only — enhances local contrast without shifting hue.

    Applied in LAB rather than BGR so package colours (which an inspector may need to
    recognise) survive intact.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def preprocess(data: bytes) -> PreprocessResult:
    """Full preprocessing pass. Never raises except on undecodable input.

    Stage order:
        decode → downscale → exposure-correct → dewarp → blur-check → deskew
        → glare-reduce → CLAHE → encode
    """
    settings = get_settings()
    degraded: list[DegradationFlag] = []

    image = decode(data)
    original_long_edge = max(image.shape[:2])
    if original_long_edge < MIN_LONG_EDGE_PX:
        degraded.append(DegradationFlag.LOW_RESOLUTION)

    image = _downscale(image, settings.max_image_edge_px)

    # --- exposure correction -------------------------------------------------
    # Correct before dewarp: perspective warp uses INTER_CUBIC which works best
    # when the source image has good dynamic range.
    image, gamma = _correct_exposure(image)

    # --- curved-label dewarp -------------------------------------------------
    # Must run before deskew: perspective correction alters the apparent rotation
    # angle, so deskew must see the flattened frame.
    image, dewarp_applied = _dewarp_curved_label(image)

    # --- sharpness gate ------------------------------------------------------
    # Measured after dewarp (warpPerspective can slightly soften) but before CLAHE
    # (which inflates Laplacian variance and would let blurry images through).
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_variance < BLUR_VARIANCE_THRESHOLD:
        degraded.append(DegradationFlag.BLURRY_IMAGE)

    # --- glare quality gate ------------------------------------------------------
    # Measured on the exposure-corrected, pre-repair frame: a highlight that the glare
    # reduction below is about to pull down is still evidence the *capture* was glared.
    # An overexposed fraction above the threshold flags the image for a retake.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    overexposed = float(np.count_nonzero(hsv[:, :, 2] >= GLARE_PIXEL_V_THRESHOLD))
    if overexposed / float(image.shape[0] * image.shape[1]) > GLARE_FRACTION_THRESHOLD:
        degraded.append(DegradationFlag.GLARED_IMAGE)

    # --- deskew --------------------------------------------------------------
    angle = _estimate_skew(gray)
    if abs(angle) > 0.5:  # sub-degree rotation costs interpolation and buys nothing
        image = _rotate(image, angle)
    else:
        angle = 0.0

    # --- glare reduction + contrast ------------------------------------------
    image = _reduce_glare(image)
    image = _enhance_contrast(image)

    ok, encoded = cv2.imencode(".png", image)
    if not ok:  # pragma: no cover - only on a broken OpenCV build
        raise ValueError("Failed to encode preprocessed image.")

    h, w = image.shape[:2]
    return PreprocessResult(
        image=image,
        png_bytes=encoded.tobytes(),
        width=w,
        height=h,
        blur_variance=blur_variance,
        deskew_angle_deg=angle,
        exposure_gamma=gamma,
        dewarp_applied=dewarp_applied,
        degraded=degraded,
    )
