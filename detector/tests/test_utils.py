import pytest

from detector import utils as utils_mod


@pytest.mark.parametrize(
    ("sid", "expected"),
    [
        ("XX.STA..HHZ", ("XX", "STA", "", "HHZ")),
        ("XX_STA__HHZ", ("XX", "STA", "", "HHZ")),
        ("FDSN:XX.STA..HHZ", ("XX", "STA", "", "HHZ")),
        ("FDSN:XX_TEST__H_H_Z", ("XX", "TEST", "", "HHZ")),
        ("", None),
        ("BAD", None),
        ("XX_STA", None),
        ("XX.STA..", None),
    ],
)
def test_parse_sid(sid, expected):
    assert utils_mod.parse_sid(sid) == expected
