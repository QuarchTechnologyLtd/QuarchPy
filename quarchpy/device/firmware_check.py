"""Checking a module's components against the versions Quarch publishes.

What was here scraped a product page on quarch.com and compared what it found
with ``float()``. It has been removed rather than patched: it read only
``fpga_1``, so a second FPGA or a fixture went unchecked; it compared both
version schemes as decimals, so an FPGA at 1.10 sorted below 1.9; it had no
timeout and caught nothing, so a slow network hung the caller; and it printed
its findings, which a GUI cannot catch and a script cannot suppress.

The replacement answers from the manifest published alongside the update files
themselves, a copy of which ships with quarchpy so that a machine with no
internet still gets an answer.
"""

import json
import os
import sys
import tempfile
from collections import namedtuple
from datetime import datetime, timezone

from quarchpy.device.device_info import split_serial

#: The copy of the published manifest that ships with quarchpy. It is read
#: rather than fetched so that a machine with no internet still gets an
#: answer; refreshing it is a separate job.
BUNDLED_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "update_manifest.json")

#: The only manifest layout this code understands. A newer one is refused
#: rather than read hopefully: a silently wrong version comparison is worse
#: than no comparison at all.
SUPPORTED_MANIFEST_FORMAT = 1

#: How the manifest writes its build time. Parsed with strptime rather than
#: datetime.fromisoformat(), which only learned to accept the trailing "Z" in
#: Python 3.11; quarchpy supports 3.7.
GENERATED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

#: Where the published manifest lives. Branch rather than tag: a tag would
#: pin customers to whatever was current when this quarchpy was released.
MANIFEST_URL = ("https://raw.githubusercontent.com/QuarchTechnologyLtd/"
                "QuarchUpdateFiles/main/manifest.json")

#: How long to wait for the manifest before giving up and using the copy we
#: have. Short on purpose: nobody should wait on a version check.
MANIFEST_TIMEOUT = 10

#: What refresh_manifest() did.
UPDATED = "updated"            # a newer manifest was downloaded
ALREADY_CURRENT = "current"    # ours matches the published one
FAILED = "failed"              # could not find out

#: What refresh_manifest() reports back.
RefreshResult = namedtuple("RefreshResult", "status path message")


def manifest_cache_dir():
    """Where a downloaded manifest is kept.

    Not beside the bundled copy: that sits inside the installed package,
    which on a managed Windows machine is often under Program Files and not
    writable by the person running the tool.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return os.path.join(base, "Quarch", "Manifest")
    return os.path.join(os.path.expanduser("~"), ".quarch", "manifest")


def cached_manifest_path():
    return os.path.join(manifest_cache_dir(), "update_manifest.json")


def cached_etag_path():
    return os.path.join(manifest_cache_dir(), "update_manifest.etag")


def _readTextFile(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _removeFile(path):
    """Deletes a file if it is there, and says nothing if it is not."""
    try:
        os.remove(path)
    except OSError:
        pass


def _writeFileAtomically(path, text):
    """Replaces a file in a single step.

    Opening the real file for writing truncates it before the first byte
    of the new content arrives. A failure in that window leaves nothing,
    and a reader arriving in it gets a fragment. Writing a temporary file
    beside it and renaming means the path is always either the old
    content or the new, never a part-written mixture. The temporary file
    goes in the same directory because a rename is only atomic within one
    filesystem.
    """
    handle, temporary = tempfile.mkstemp(dir=os.path.dirname(path),
                                         suffix=".part")
    try:
        with os.fdopen(handle, "w", encoding="utf-8",
                       newline="\n") as part:
            part.write(text)
        os.replace(temporary, path)
    except Exception:
        _removeFile(temporary)
        raise


def _isReadableManifest(text):
    """True if this text is a manifest layout we can actually use.

    Checked before the cache is written, so a captive-portal login page, a
    404 body or a truncated download can never replace a good copy.
    """
    try:
        manifest = json.loads(text, parse_float=str)
    except (TypeError, ValueError):
        return False
    if not (isinstance(manifest, dict)
            and manifest.get("manifest_format") == SUPPORTED_MANIFEST_FORMAT
            and isinstance(manifest.get("products"), dict)):
        return False

    catalogue = Catalogue(manifest["products"])
    try:
        for product_number in catalogue.product_numbers:
            for hardware_version in catalogue.hardware_versions(
                    product_number):
                catalogue.files_for(product_number, hardware_version)
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _manifestGeneratedAt(text):
    """When a manifest was built, read from its text, or None."""
    try:
        manifest = json.loads(text, parse_float=str)
    except (TypeError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    return parse_generated(manifest.get("generated"))


def _preferredManifest():
    """Which manifest to read: the downloaded one, or the one quarchpy ships.

    Normally the cache, because that is the refreshed copy. But installing a
    newer quarchpy brings a newer bundled manifest with it, and a cache from
    before that upgrade would otherwise keep answering with older versions
    for ever, every time a refresh cannot be made.

    A copy with no build time at all predates the field, so a dated copy
    wins over an undated one either way round.
    """
    cachedText = _readTextFile(cached_manifest_path()) or ""
    if not _isReadableManifest(cachedText):
        return BUNDLED_MANIFEST

    cachedAt = _manifestGeneratedAt(cachedText)
    bundledAt = _manifestGeneratedAt(_readTextFile(BUNDLED_MANIFEST) or "")

    if bundledAt is not None and (cachedAt is None or bundledAt > cachedAt):
        return BUNDLED_MANIFEST
    return cached_manifest_path()


def refresh_manifest(url=None, timeout=MANIFEST_TIMEOUT):
    """Downloads the published manifest if ours is not already current.

    Sends the stored ETag, so when nothing has changed the server answers
    304 and no body is transferred at all.

    Args:
        url: where to fetch from. None reads MANIFEST_URL when the call is
            made rather than when this module was imported, so setting it
            at runtime, to a mirror for instance, takes effect.
        timeout: seconds to wait.

    Returns:
        A RefreshResult. status is UPDATED, ALREADY_CURRENT or FAILED.
        FAILED is not an error to raise on: a machine with no route to
        GitHub is expected, and the caller carries on with the copy it has,
        saying so.
    """
    import requests

    url = url or MANIFEST_URL

    headers = {}
    # Only offer the ETag when the cached manifest is readable. Offering it
    # because the file merely exists means a damaged cache is answered with
    # 304 for ever: the server agrees nothing changed, nothing is
    # downloaded, and the broken copy is never replaced.
    etag = _readTextFile(cached_etag_path())
    if etag and _isReadableManifest(_readTextFile(cached_manifest_path()) or ""):
        headers["If-None-Match"] = etag.strip()

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        # Deliberately broad. Whatever went wrong, the answer is the same:
        # use the copy we have and tell the user we could not check.
        return RefreshResult(FAILED, None,
                             "could not reach {0}: {1}".format(url, e))

    if response.status_code == 304:
        return RefreshResult(ALREADY_CURRENT, cached_manifest_path(),
                             "already the published version")

    if response.status_code != 200:
        # A private or renamed repository answers 404, the same as a typo in
        # the path, so do not guess which it was.
        return RefreshResult(FAILED, None,
                             "{0} returned HTTP {1}".format(
                                 url, response.status_code))

    text = response.text
    if not _isReadableManifest(text):
        return RefreshResult(FAILED, None,
                             "{0} did not return a readable manifest".format(
                                 url))

    try:
        os.makedirs(manifest_cache_dir(), exist_ok=True)
        _removeFile(cached_etag_path())
        _writeFileAtomically(cached_manifest_path(), text)

        newEtag = response.headers.get("ETag")
        if newEtag:
            _writeFileAtomically(cached_etag_path(), newEtag)
    except OSError as e:
        return RefreshResult(FAILED, None,
                             "downloaded, but could not save it: {0}".format(e))

    return RefreshResult(UPDATED, cached_manifest_path(),
                         "downloaded the published manifest")

#: What a component's version was found to be.
UP_TO_DATE = "up to date"
UPDATE_AVAILABLE = "update available"
UNKNOWN = "unknown"

#: How each reads in a table. A module ahead of the published version shows
#: "?" with that version in brackets: the user sees a smaller number than
#: the one they are running, which explains the "?" without a fourth symbol.
STATUS_SYMBOLS = {
    UP_TO_DATE: "✓",
    UPDATE_AVAILABLE: "↑",
    UNKNOWN: "?",
}

#: For consoles that cannot print the above. A Windows console is usually
#: cp1252, which has neither a tick nor an up arrow, and printing one there
#: raises UnicodeEncodeError part way through the table.
STATUS_SYMBOLS_PLAIN = {
    UP_TO_DATE: "OK",
    UPDATE_AVAILABLE: "NEW",
    UNKNOWN: "?",
}


def status_symbol(status, stream=None):
    """How to show a status on this console.

    Args:
        status: UP_TO_DATE, UPDATE_AVAILABLE or UNKNOWN.
        stream: where it is going, stdout by default.

    Returns:
        The symbol, or a plain-text stand-in where the console cannot print
        it. Checked rather than assumed: the alternative is a table that
        raises half way down on a machine we never tested on.
    """
    symbol = STATUS_SYMBOLS.get(status, "?")
    encoding = getattr(stream or sys.stdout, "encoding", None)
    try:
        symbol.encode(encoding or "ascii")
    except (UnicodeEncodeError, LookupError, TypeError):
        return STATUS_SYMBOLS_PLAIN.get(status, "?")
    return symbol


def _versionParts(version):
    """Turns "6.016" into (6, 16), or None if it cannot be read.

    Versions are always published with the minor at its full width, so
    "6.020" and never "6.02", which is what makes comparing the two halves
    as integers correct. A version with no minor at all does occur, QTL2266
    firmware is published as "5", and reads as (5, 0).
    """
    if version is None:
        return None

    text = str(version).strip()
    if not text:
        return None

    major, _, minor = text.partition(".")
    try:
        return (int(major), int(minor) if minor else 0)
    except ValueError:
        return None


def compare_versions(current, latest):
    """Compares two versions.

    Returns:
        -1 if current is older than latest, 0 if they are the same, 1 if
        current is ahead of it, and None if either could not be read. None
        rather than a guess: a wrong answer here is reported to the user as
        fact.
    """
    here = _versionParts(current)
    there = _versionParts(latest)
    if here is None or there is None:
        return None
    return (here > there) - (here < there)


def status_for(current, latest):
    """What to report for a component, given what is published for it.

    A module ahead of the published version is UNKNOWN, not UP_TO_DATE. It
    is usually a pre-release build, and telling someone running 6.021 that
    6.016 is the latest is only useful if it is not dressed up as a tick.
    """
    comparison = compare_versions(current, latest)
    if comparison is None:
        return UNKNOWN
    if comparison < 0:
        return UPDATE_AVAILABLE
    if comparison > 0:
        return UNKNOWN
    return UP_TO_DATE


#: Which published boot type answers for each field a module reports.
BOOT_TYPE_FOR_FIELD = {
    "firmware": "Firmware",
    "fpga_1": "FPGA",
    "fpga_2": "FPGA",
    "fpga_3": "FPGA",
    "fpga_4": "FPGA",
    "fixture_fpga": "FPGA",
}

#: What was found for one component.
#:
#: latestV is None when nothing is published for it, which is not the same
#: as being up to date and must never be shown as one.
ComponentStatus = namedtuple("ComponentStatus",
                             "role part_number currentV latestV status")


def _asText(value):
    """A manifest value as the text it was published as, or None."""
    return None if value is None else str(value)


def parse_generated(generated):
    """Turns a manifest build time into an aware UTC datetime.

    Args:
        generated: the manifest's "generated" value, or None.

    Returns:
        A timezone-aware datetime, or None if it is absent or unreadable. A
        date we cannot read is treated as no date at all: the caller tells
        the user the age is unknown rather than showing something wrong.
    """
    if not generated:
        return None
    try:
        stamp = datetime.strptime(str(generated).strip(), GENERATED_FORMAT)
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=timezone.utc)


#: One publishable file, as the manifest describes it.
#:
#: ``part_number`` is the component the file updates, which is not the product
#: it goes in: the file for a QTL2347 fixture is published as QTL2535. A
#: module reports yet another number for that same component, QTL2129, so
#: ``targets`` carries the header's FirmwareTarget list, which is the only
#: thing connecting the three.
CatalogueFile = namedtuple(
    "CatalogueFile",
    "product_number hardware_version path boot_type part_number version "
    "targets sha256 size")


class Catalogue:
    """The published list of update files, indexed by product.

    This knows what has been published. It does not know what a module is
    running and compares nothing; that is check_for_updates().
    """

    def __init__(self, products, path=None, generated=None, verified=False):
        self._products = products
        #: Where this was read from, so a caller can tell the user which copy
        #: an answer came from.
        self.path = path
        #: Whether this was confirmed to be the published version. False
        #: means the answers may be out of date, and "up to date" must be
        #: reported with that caveat rather than as a plain yes.
        self.verified = verified
        #: When this manifest was built, as published. Kept as text for
        #: showing the user; generated_utc parses it. None in a manifest
        #: written before the field existed.
        self.generated = generated

    @classmethod
    def load(cls, path=None):
        """Reads a manifest from disk. Never touches the network.

        Reads whichever of the downloaded copy and the bundled one was
        built most recently, so a refresh takes effect without writing
        inside the installed package, and upgrading quarchpy is not undone
        by a cache left over from before it. If the cached copy cannot be
        read the bundled one is used, because a damaged cache should cost
        accuracy, not the whole feature.

        Args:
            path: a manifest to read instead of the usual ones.

        Returns:
            A Catalogue.

        Raises:
            ValueError: the file is not a manifest layout this code reads.
        """
        if path is None:
            path = _preferredManifest()

        with open(path, encoding="utf-8") as manifest_file:
            # parse_float=str, always. FirmwareVersion is a JSON number, and
            # a plain load turns "5.000" into 5.0 and "1.10" into 1.1, which
            # is wrong for firmware and for FPGA versions in opposite
            # directions. Keep every version as the text it was published as.
            manifest = json.load(manifest_file, parse_float=str)

        manifest_format = manifest.get("manifest_format")
        if manifest_format != SUPPORTED_MANIFEST_FORMAT:
            raise ValueError(
                "{0} is manifest format {1!r}; this quarchpy reads {2}. "
                "Update quarchpy.".format(path, manifest_format,
                                          SUPPORTED_MANIFEST_FORMAT))

        return cls(manifest.get("products") or {}, path=path,
                   generated=manifest.get("generated"))

    @classmethod
    def load_latest(cls, timeout=MANIFEST_TIMEOUT, allow_download=True,
                    url=None):
        """Loads the manifest, refreshing it first where it can.

        Saying "up to date" means nothing unless the list being compared
        against is the current one, so the check refreshes by default.
        Scanning does not: Catalogue.load() stays local, and only a version
        check pays for the network.

        Args:
            timeout: seconds to wait for the download.
            allow_download: False to use what is on disk without asking.
            url: where to fetch from, defaulting to MANIFEST_URL.

        Returns:
            (Catalogue, RefreshResult). The catalogue is usable either way;
            its verified flag says whether its answers can be trusted as
            current, and the result carries a message to show the user when
            they cannot.
        """
        if not allow_download:
            return cls.load(), RefreshResult(FAILED, None, "not checked")

        result = refresh_manifest(url=url, timeout=timeout)
        catalogue = cls.load()

        # The refresh confirms the cached copy, so it says nothing about a
        # catalogue that fell back to the bundled one. Claiming otherwise is
        # how a damaged cache ends up reported as checked and current.
        confirmed = result.status in (UPDATED, ALREADY_CURRENT)
        catalogue.verified = bool(
            confirmed and result.path
            and os.path.abspath(catalogue.path or "")
            == os.path.abspath(result.path))
        return catalogue, result

    @property
    def generated_utc(self):
        """When this manifest was built, or None if it does not say."""
        return parse_generated(self.generated)

    @property
    def product_numbers(self):
        """Every product the manifest publishes files for."""
        return sorted(self._products)

    def hardware_versions(self, product_number):
        """Every hardware version this product publishes files for.

        Args:
            product_number: the product, for example "QTL1999".

        Returns:
            A sorted list such as ["05", "06", "07", "08"], empty when the
            product is not published here.
        """
        product = self._products.get(str(product_number).strip().upper())
        if not product:
            return []

        versions = set()
        for hardware in (product.get("hardware") or {}).values():
            versions.update(hardware.get("hardware_versions") or [])
        return sorted(versions)

    def files_for(self, product_number, hardware_version=None):
        """Every published file for a product.

        Args:
            product_number: the product, for example "QTL1999". The number
                printed on the box, not the component inside it.
            hardware_version: the two-digit hardware version, for example
                "06". Omit it for the files covering every hardware version.

        Returns:
            A list of CatalogueFile, in manifest order. Empty when there is
            no entry, which means "not published here" and never "up to
            date".
        """
        product = self._products.get(str(product_number).strip().upper())
        if not product:
            return []

        wanted = (str(hardware_version).strip()
                  if hardware_version is not None else None)

        found = []
        for hardware in (product.get("hardware") or {}).values():
            # hardware_versions is written out in full, so this is a
            # membership test rather than a range to parse.
            versions = hardware.get("hardware_versions") or []
            if wanted is not None and wanted not in versions:
                continue

            for entry in hardware.get("files") or []:
                header = entry.get("header") or {}
                found.append(CatalogueFile(
                    product_number=str(product_number).strip().upper(),
                    hardware_version=wanted,
                    path=entry.get("path"),
                    boot_type=entry.get("boot_type"),
                    part_number=entry.get("firmware_part_number"),
                    version=_asText(entry.get("firmware_version")),
                    targets=tuple(header.get("FirmwareTarget") or ()),
                    sha256=entry.get("sha256"),
                    size=entry.get("size")))

        return found

def _publishedVersions(catalogue, product_number, hardware_version):
    """{boot type: version} for one product and hardware version.

    Empty when either is unknown. Deliberately not "every hardware version
    of this product": a QTL3236-01 and a QTL3236-02 are published different
    firmware, and no .qfw file would refuse the wrong one.
    """
    if not product_number or not hardware_version:
        return {}

    published = {}
    for entry in catalogue.files_for(product_number, hardware_version):
        published[entry.boot_type] = entry.version
    return published


def check_for_updates(device_info, catalogue=None):
    """What is published for each component this module reported.

    Args:
        device_info: the module, as a scan found it.
        catalogue: the published list. Loaded from disk if not given, which
            does not touch the network. Pass one from
            Catalogue.load_latest() when the answers need to be current.

    Returns:
        A list of ComponentStatus, one per component the module reported.
        Empty if it reported none.
    """
    if catalogue is None:
        catalogue = Catalogue.load()

    product, hardware = split_serial(
        getattr(device_info, "user_level_serial_number", None))
    moduleVersions = _publishedVersions(catalogue, product, hardware)

    # A fixture is its own product and its FPGA is published under its own
    # number, so it is looked up separately. Without a part number for it we
    # report nothing rather than falling back to the module's own product:
    # that would offer the module's FPGA image as a fixture update.
    fixtureProduct, fixtureHardware = split_serial(
        getattr(device_info, "fixture_part_number", None))
    fixtureVersions = _publishedVersions(catalogue, fixtureProduct,
                                         fixtureHardware)

    found = []
    for field, part_number, version in device_info.components:
        if field == "fixture_fpga":
            latest = fixtureVersions.get("FPGA")
        else:
            latest = moduleVersions.get(BOOT_TYPE_FOR_FIELD.get(field))
        found.append(ComponentStatus(field, part_number, version, latest,
                                     status_for(version, latest)))
    return found


#: Loaded once per process, so a scan of twenty modules does not ask twenty
#: times. forget_catalogue() clears it.
_sharedCatalogue = None


def shared_catalogue(refresh=True):
    """The catalogue this process uses, fetched at most once."""
    global _sharedCatalogue
    if _sharedCatalogue is None:
        if refresh:
            _sharedCatalogue, _ = Catalogue.load_latest()
        else:
            _sharedCatalogue = Catalogue.load()
    return _sharedCatalogue


def forget_catalogue():
    """Drops the shared catalogue, so the next call loads it again."""
    global _sharedCatalogue
    _sharedCatalogue = None


def is_update_available(device_info):
    """Whether a newer firmware or FPGA version is published for this module.

    Args:
        device_info: the ``DeviceInfo`` to check.

    Returns:
        True if any component has a newer published version. False covers
        both "everything is current" and "we could not tell", so a caller
        that needs to know which should use check_for_updates().
    """
    return any(component.status == UPDATE_AVAILABLE
               for component in check_for_updates(device_info,
                                                  shared_catalogue()))
