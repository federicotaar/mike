"""Frozen entry point, separate from package-relative Python startup."""
import sys
if '--smoke-test' in sys.argv:
    from desktop.smoke import main
else:
    from desktop.__main__ import main
main()
