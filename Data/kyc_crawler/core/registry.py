"""
Anh xa "ten site trong config" -> "ham parse tuong ung".
Them site moi = them 1 dong o day + 1 file trong parsers/.
"""

from parsers import masothue

PARSERS = {
    "masothue": masothue.parse,
    # "dangkykinhdoanh": dangkykinhdoanh.parse,   # them khi da viet xong
    # "tratencongty": tratencongty.parse,          # them khi da viet xong
}


def get_parser(source_name: str):
    parser = PARSERS.get(source_name)
    if parser is None:
        raise ValueError(f"Chua co parser cho nguon '{source_name}'")
    return parser
