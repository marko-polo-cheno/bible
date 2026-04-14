"""Static category tree constants derived from raw_categories_en.html and raw_categories_zh.html."""

from typing import Any


def _node(name: str, value: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"name": name, "value": value, "children": children or []}


CATEGORIES_EN: list[dict[str, Any]] = [
    _node("Media", "Media", [
        _node("Sermon", "Media/Sermon"),
        _node("Lecture", "Media/Lecture"),
        _node("Testimony", "Media/Testimony"),
    ]),
    _node("Books", "Books", [
        _node("Book", "Books/Book", [
            _node("Basic Beliefs", "Books/Book/Basic Beliefs", [
                _node("Outreach Series", "Books/Book/Basic Beliefs/Outreach Series"),
                _node("Gospel Series", "Books/Book/Basic Beliefs/Gospel Series"),
                _node("Inquiry Series", "Books/Book/Basic Beliefs/Inquiry Series"),
                _node("Doctrinal Series", "Books/Book/Basic Beliefs/Doctrinal Series"),
                _node("Testimony Series", "Books/Book/Basic Beliefs/Testimony Series"),
            ]),
            _node("Christian Living", "Books/Book/Christian Living", [
                _node("Discipleship Series", "Books/Book/Christian Living/Discipleship Series"),
            ]),
            _node("Biblical References", "Books/Book/Biblical References", [
                _node("Bible Study Guides", "Books/Book/Biblical References/Bible Study Guides"),
                _node("Bible Curriculum", "Books/Book/Biblical References/Bible Curriculum"),
                _node("Topical Studies", "Books/Book/Biblical References/Topical Studies"),
            ]),
            _node("Religious Education", "Books/Book/Religious Education", [
                _node("Textbooks", "Books/Book/Religious Education/Textbooks", [
                    _node("Kindergarten", "Books/Book/Religious Education/Textbooks/Kindergarten"),
                    _node("Elementary 1", "Books/Book/Religious Education/Textbooks/Elementary 1"),
                    _node("Elementary 2", "Books/Book/Religious Education/Textbooks/Elementary 2"),
                    _node("Junior 1", "Books/Book/Religious Education/Textbooks/Junior 1"),
                    _node("Junior 2", "Books/Book/Religious Education/Textbooks/Junior 2"),
                ]),
                _node("Student Workbooks", "Books/Book/Religious Education/Student Workbooks", [
                    _node("Elementary 2", "Books/Book/Religious Education/Student Workbooks/Elementary 2"),
                    _node("Junior 1", "Books/Book/Religious Education/Student Workbooks/Junior 1"),
                    _node("Junior 2", "Books/Book/Religious Education/Student Workbooks/Junior 2"),
                ]),
                _node("Student Spiritual Convocation", "Books/Book/Religious Education/Student Spiritual Convocation"),
                _node("Manuals", "Books/Book/Religious Education/Manuals"),
            ]),
        ]),
    ]),
    _node("Magazines", "Magazines", [
        _node("Magazine", "Magazines/Magazine", [
            _node("Manna Magazine", "Magazines/Magazine/Manna Magazine"),
            _node("Living Water", "Magazines/Magazine/Living Water"),
            _node("Showers of Blessing", "Magazines/Magazine/Showers of Blessing"),
            _node("Heavenly Sunlight", "Magazines/Magazine/Heavenly Sunlight"),
        ]),
    ]),
    _node("Training Materials", "Training Materials", [
        _node("Lecture Notes", "Training Materials/Lecture Notes"),
    ]),
    _node("Unknown", "Unknown"),
]

CATEGORIES_ZH: list[dict[str, Any]] = [
    _node("影音", "影音", [
        _node("講道", "影音/講道"),
        _node("講習會", "影音/講習會"),
        _node("見證", "影音/見證"),
    ]),
    _node("書籍", "書籍", [
        _node("書籍", "書籍/書籍", [
            _node("釋義類", "書籍/書籍/釋義類", [
                _node("釋義叢書", "書籍/書籍/釋義類/釋義叢書"),
            ]),
            _node("研經類", "書籍/書籍/研經類"),
            _node("查經類", "書籍/書籍/查經類"),
            _node("福音類", "書籍/書籍/福音類", [
                _node("福音小冊", "書籍/書籍/福音類/福音小冊"),
                _node("教義叢書", "書籍/書籍/福音類/教義叢書"),
            ]),
        ]),
    ]),
    _node("雜誌", "雜誌", [
        _node("雜誌", "雜誌/雜誌", [
            _node("聖靈月刊", "雜誌/雜誌/聖靈月刊", [
                _node("喜信網類別", "雜誌/雜誌/聖靈月刊/喜信網類別", [
                    _node("專題報導", "雜誌/雜誌/聖靈月刊/喜信網類別/專題報導"),
                    _node("海外來鴻", "雜誌/雜誌/聖靈月刊/喜信網類別/海外來鴻"),
                    _node("宗教教育", "雜誌/雜誌/聖靈月刊/喜信網類別/宗教教育"),
                    _node("藝文特區", "雜誌/雜誌/聖靈月刊/喜信網類別/藝文特區"),
                    _node("情詞愛語", "雜誌/雜誌/聖靈月刊/喜信網類別/情詞愛語"),
                    _node("你來我往", "雜誌/雜誌/聖靈月刊/喜信網類別/你來我往"),
                    _node("自由來稿", "雜誌/雜誌/聖靈月刊/喜信網類別/自由來稿"),
                    _node("主題特寫", "雜誌/雜誌/聖靈月刊/喜信網類別/主題特寫"),
                    _node("編輯手記", "雜誌/雜誌/聖靈月刊/喜信網類別/編輯手記"),
                    _node("時勢評論", "雜誌/雜誌/聖靈月刊/喜信網類別/時勢評論"),
                    _node("真理論壇", "雜誌/雜誌/聖靈月刊/喜信網類別/真理論壇"),
                    _node("靈修小品", "雜誌/雜誌/聖靈月刊/喜信網類別/靈修小品"),
                    _node("信仰社會", "雜誌/雜誌/聖靈月刊/喜信網類別/信仰社會"),
                    _node("見證見證", "雜誌/雜誌/聖靈月刊/喜信網類別/見證見證"),
                ]),
                _node("真理", "雜誌/雜誌/聖靈月刊/真理", [
                    _node("論道", "雜誌/雜誌/聖靈月刊/真理/論道"),
                ]),
                _node("卷頭言", "雜誌/雜誌/聖靈月刊/卷頭言"),
                _node("封面說明", "雜誌/雜誌/聖靈月刊/封面說明"),
                _node("福音", "雜誌/雜誌/聖靈月刊/福音"),
                _node("簡道", "雜誌/雜誌/聖靈月刊/簡道"),
                _node("講台", "雜誌/雜誌/聖靈月刊/講台"),
                _node("查經", "雜誌/雜誌/聖靈月刊/查經"),
                _node("靈修", "雜誌/雜誌/聖靈月刊/靈修"),
                _node("蒙恩見證", "雜誌/雜誌/聖靈月刊/蒙恩見證"),
                _node("信徒園地", "雜誌/雜誌/聖靈月刊/信徒園地"),
                _node("國內消息", "雜誌/雜誌/聖靈月刊/國內消息"),
                _node("國外消息", "雜誌/雜誌/聖靈月刊/國外消息"),
            ]),
            _node("青年團契", "雜誌/雜誌/青年團契"),
            _node("宗教教育", "雜誌/雜誌/宗教教育"),
            _node("聖靈報", "雜誌/雜誌/聖靈報", [
                _node("蒙恩見證", "雜誌/雜誌/聖靈報/蒙恩見證"),
            ]),
        ]),
    ]),
    _node("教材", "教材", [
        _node("教材", "教材/教材", [
            _node("幼年班", "教材/教材/幼年班"),
            _node("高級班", "教材/教材/高級班"),
            _node("神學院", "教材/教材/神學院"),
        ]),
    ]),
    _node("未分類", "未分類"),
]


def get_category_tree(lang_id: int) -> list[dict[str, Any]]:
    return CATEGORIES_ZH if lang_id == 2 else CATEGORIES_EN


def _build_leaf_index(nodes: list[dict[str, Any]], parent_path: str = "") -> dict[str, list[str]]:
    """Build {node_name -> [full_value_paths]} index for all nodes in the tree."""
    index: dict[str, list[str]] = {}
    for node in nodes:
        name = node["name"]
        value = node["value"]
        if name not in index:
            index[name] = []
        index[name].append(value)
        if node.get("children"):
            child_index = _build_leaf_index(node["children"], value)
            for k, v in child_index.items():
                if k not in index:
                    index[k] = []
                index[k].extend(v)
    return index


LEAF_INDEX_EN = _build_leaf_index(CATEGORIES_EN)
LEAF_INDEX_ZH = _build_leaf_index(CATEGORIES_ZH)


def get_leaf_index(lang_id: int) -> dict[str, list[str]]:
    return LEAF_INDEX_ZH if lang_id == 2 else LEAF_INDEX_EN
