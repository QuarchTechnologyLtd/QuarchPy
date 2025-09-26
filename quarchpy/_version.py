from packaging.version import Version

__version__ = "2.2.12.dev2"

# Parse the version string into a Version object
parsed_version = Version(__version__)

# Check the specific attribute for development releases
if parsed_version.is_devrelease:
    print(f"'{__version__}' is a development release.")
else:
    print(f"'{__version__}' is not a development release.")

# --- Example with a final release ---
stable_version_str = "2.2.12"
stable_version = Version(stable_version_str)
print(f"Is '{stable_version_str}' a dev release? {stable_version.is_devrelease}")