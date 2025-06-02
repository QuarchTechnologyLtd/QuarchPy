import pytest
from quarchpy.device.scanDevices import *

def test_scan_devices():
    """

    Returns:

    """

    v=scanDevices(target_conn="tcp").values()
    b = ["QTL","no device"]
    res = list(filter(lambda x: "QTL" in x, v))
    if len(res)>0 or len(v)==0: # passes if QTL in one of the valeus, or if no devices are scanned
        result = True
    else:
        result= False
    assert result is True

if __name__ == "__main__":
    test_scan_devices()