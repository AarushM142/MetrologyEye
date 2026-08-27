"""Pipeline services. Each module is independently importable and degrades on its own.

Stage order: preprocess -> scale -> ocr -> extract -> fuse -> rules -> notice.
"""
