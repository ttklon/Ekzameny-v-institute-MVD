#!/usr/bin/env python3
"""Сборка ответов на экзаменационные вопросы в документ Word.

Запуск:
    python .github/answers/build_docx.py adp 1 10         — документ на вопросы 1–10
    python .github/answers/build_docx.py adp 1 149 --one  — один документ на все вопросы (с содержанием)
    python .github/answers/build_docx.py adp --all        — все документы по десять вопросов и общий документ
    python .github/answers/build_docx.py adp2 --sample    — один документ на те вопросы, которые уже написаны
                                                            (номера могут идти не подряд)

Коды: adp — вариант 1 («Подробные ответы»), adp2 — вариант 2 («Сокращённые ответы») по административной
деятельности полиции; krim — криминалистика (криминалистическая тактика);
ugp — уголовное право (ответы сразу на оба перечня; сопоставление — в .github/answers/ugp/map.tsv);
upp — уголовно-процессуальное право (ответы сразу на оба перечня: к экзамену и к зачёту;
какой ответ закрывает какой вопрос — в .github/answers/upp/map.tsv, по нему в общий документ
ставятся указатели «вопрос экзамена → ответ» и «вопрос зачёта → ответ»).

Готовые документы кладутся в папку варианта ответов:
    <Дисциплина>/3. Ответы на вопросы/<Вариант>/

Исходный текст ответов лежит в .github/answers/<код>/*.txt в простой разметке:
    # Вопрос N. …      — заголовок вопроса
    ## …               — подзаголовок
    > …                — определение (абзац с линией слева)
    !! …               — «Главное для запоминания» (абзац в рамке)
    - …                — пункт перечня
      - …              — пункт перечня второго уровня (два пробела перед дефисом)
    **…**  //…//  __…__ — полужирный, курсив, подчёркивание

Оформление: шрифт PT Astra Serif, одинарный межстрочный интервал,
после каждого вопроса — пять пустых абзацев.
"""
import glob
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT = "PT Astra Serif"
BODY_PT = 14
EMPTY_AFTER_QUESTION = 5

DISCIPLINES = {
    "adp": "Административная деятельность полиции",
    "adp2": "Административная деятельность полиции",
    "upp": "Уголовно-процессуальное право",
    "krim": "Криминалистика",
    "ugp": "Уголовное право",
}

# Папка варианта ответов внутри «3. Ответы на вопросы». У дисциплины может быть несколько вариантов
# ответов (разный стиль или объём); у каждого варианта — своя папка с исходным текстом и своя папка с документами.
VARIANTS = {
    "adp": "Вариант 1. Подробные ответы",
    "adp2": "Вариант 2. Сокращённые ответы",
    "upp": "Вариант 1. Краткие ответы (экзамен и зачёт)",
    "krim": "Вариант 1. Краткие ответы",
    "ugp": "Вариант 1. Краткие ответы (оба перечня)",
}

# Дисциплины с несколькими перечнями вопросов: (подпись перечня, признак в имени файла перечня[, номер блока]).
# Признак, начинающийся с «^», сравнивается с началом имени файла. Номер блока нужен, когда в одном файле
# нумерация начинается заново (второй перечень по уголовному праву: Общая часть 1–50, Особенная часть 1–43).
LISTS = {
    "upp": (("экзамен", "экзамену"), ("зачёт", "зачету")),
    "ugp": (("перечень 1", "^Примерный"), ("перечень 2, Общая часть", "^еще один", 0),
            ("перечень 2, Особенная часть", "^еще один", 1)),
}
# Пояснение в начале общего документа.
INTRO = {
    "upp": "Ответы закрывают оба перечня: 66 вопросов к экзамену и 87 вопросов к зачёту. Вопросы, которые "
           "повторяются или пересекаются, сведены в один ответ, поэтому ответов 108. Под заголовком каждого ответа "
           "указано, какие вопросы экзамена и зачёта он закрывает; найти ответ по номеру вопроса помогают два "
           "указателя после содержания. Статьи без названия закона — статьи Уголовно-процессуального кодекса "
           "Российской Федерации (УПК) в редакции на 06.08.2026. УК — Уголовный кодекс Российской Федерации; "
           "Пленум — постановление Пленума Верховного Суда Российской Федерации; КС РФ — Конституционный Суд "
           "Российской Федерации.",
    "ugp": "Ответы закрывают оба перечня вопросов к экзамену: первый — 107 вопросов, второй — 93 вопроса "
           "(Общая часть — 50, Особенная часть — 43). Совпадающие вопросы сведены в один ответ, поэтому ответов 117: "
           "1–55 — Общая часть, 56–117 — Особенная часть. Под заголовком каждого ответа указано, какие вопросы "
           "перечней он закрывает; найти ответ по номеру вопроса помогают указатели после содержания. "
           "В первом перечне номер 63 стоит дважды, а номера 64 нет: второй из этих вопросов (о вовлечении "
           "несовершеннолетнего в совершение преступления) учтён как вопрос 64. УК РФ — Уголовный кодекс "
           "Российской Федерации; Пленум — постановление Пленума Верховного Суда Российской Федерации.",
    "krim": "Ответы на вопросы примерного перечня по криминалистической тактике. УПК РФ — Уголовно-процессуальный "
            "кодекс Российской Федерации в редакции на 06.08.2026; УК РФ — Уголовный кодекс Российской Федерации; "
            "Пленум — постановление Пленума Верховного Суда Российской Федерации. Определения, классификации "
            "и тактические рекомендации взяты из учебников и пособий папки «2. Источники»; нормы закона "
            "сверены с текстами актов из той же папки.",
}
PER_FILE = 10

# Сокращённые названия актов: (шаблон сокращения, сокращение, полное название, признак полного названия).
# Сокращение попадает в справку под заголовком вопроса, только если в самом ответе
# полное название акта не приведено (ответ на каждый вопрос должен читаться отдельно).
ABBR = [
    (r"УК РФ", "УК РФ", "Уголовный кодекс Российской Федерации", "Уголовный кодекс Российской Федерации"),
    (r"Закон\w* о полиции", "Закон о полиции",
     "Федеральный закон от 07.02.2011 № 3-ФЗ «О полиции»", "№ 3-ФЗ «О полиции»"),
    (r"Закон\w* о службе", "Закон о службе",
     "Федеральный закон от 30.11.2011 № 342-ФЗ «О службе в органах внутренних дел Российской Федерации "
     "и внесении изменений в отдельные законодательные акты Российской Федерации»", "№ 342-ФЗ «О службе"),
    (r"Закон\w* о профилактике", "Закон о профилактике",
     "Федеральный закон от 23.06.2016 № 182-ФЗ «Об основах системы профилактики правонарушений "
     "в Российской Федерации»", "№ 182-ФЗ «Об основах системы профилактики"),
    (r"Закон\w* о безопасности|Федеральн\w+ закон\w* «О безопасности»", "Закон о безопасности",
     "Федеральный закон от 28.12.2010 № 390-ФЗ «О безопасности»", "№ 390-ФЗ «О безопасности»"),
    (r"Закон\w* о Правительстве", "Закон о Правительстве",
     "Федеральный конституционный закон от 06.11.2020 № 4-ФКЗ «О Правительстве Российской Федерации»",
     "№ 4-ФКЗ «О Правительстве"),
    (r"Закон\w* о прокуратуре|«О прокуратуре Российской Федерации»", "Закон о прокуратуре",
     "Федеральный закон от 17.01.1992 № 2202-1 «О прокуратуре Российской Федерации»", "№ 2202-1"),
    (r"Закон\w* № 8-ФЗ", "Закон № 8-ФЗ",
     "Федеральный закон от 09.02.2009 № 8-ФЗ «Об обеспечении доступа к информации о деятельности "
     "государственных органов и органов местного самоуправления»", "№ 8-ФЗ «Об обеспечении доступа"),
    (r"№ 44-ФЗ", "Закон № 44-ФЗ",
     "Федеральный закон от 02.04.2014 № 44-ФЗ «Об участии граждан в охране общественного порядка»",
     "№ 44-ФЗ «Об участии граждан"),
    (r"№ 212-ФЗ", "Закон № 212-ФЗ",
     "Федеральный закон от 21.07.2014 № 212-ФЗ «Об основах общественного контроля в Российской Федерации»",
     "№ 212-ФЗ «Об основах общественного контроля"),
    (r"№ 59-ФЗ", "Закон № 59-ФЗ",
     "Федеральный закон от 02.05.2006 № 59-ФЗ «О порядке рассмотрения обращений граждан "
     "Российской Федерации»", "№ 59-ФЗ «О порядке рассмотрения"),
    (r"№ 131-ФЗ", "Закон № 131-ФЗ",
     "Федеральный закон от 06.10.2003 № 131-ФЗ «Об общих принципах организации местного самоуправления "
     "в Российской Федерации»", "№ 131-ФЗ «Об общих принципах"),
    (r"№ 226-ФЗ", "Закон № 226-ФЗ",
     "Федеральный закон от 03.07.2016 № 226-ФЗ «О войсках национальной гвардии Российской Федерации»",
     "№ 226-ФЗ «О войсках"),
    (r"(?<!\d)№ 54-ФЗ", "Закон № 54-ФЗ",
     "Федеральный закон от 19.06.2004 № 54-ФЗ «О собраниях, митингах, демонстрациях, шествиях "
     "и пикетированиях»", "№ 54-ФЗ «О собраниях"),
    (r"(?<!\d)№ 64-ФЗ", "Закон № 64-ФЗ",
     "Федеральный закон от 06.04.2011 № 64-ФЗ «Об административном надзоре за лицами, освобожденными "
     "из мест лишения свободы»", "№ 64-ФЗ «Об административном надзоре"),
    (r"Положени\w+ о МВД", "Положение о МВД",
     "Положение о Министерстве внутренних дел Российской Федерации, утверждённое Указом Президента "
     "Российской Федерации от 21.12.2016 № 699", ("о Министерстве внутренних дел Российской Федерации, утв.",
                                                  "о МВД России, утв. Указом",
                                                  "о Министерстве внутренних дел Российской Федерации** (далее")),
    (r"Типов\w+ положени\w+", "Типовое положение",
     "Типовое положение о территориальном органе Министерства внутренних дел Российской Федерации "
     "по субъекту Российской Федерации, утверждённое Указом Президента Российской Федерации "
     "от 21.12.2016 № 699", ("о территориальном органе МВД России по субъекту РФ, утв.",
                            "о территориальном органе МВД России по субъекту Российской Федерации, утв.",
                            "о территориальном органе МВД России по субъекту Российской Федерации** (далее")),
    (r"Закон\w* о социальных гарантиях", "Закон о социальных гарантиях",
     "Федеральный закон от 19.07.2011 № 247-ФЗ «О социальных гарантиях сотрудникам органов внутренних дел "
     "Российской Федерации и внесении изменений в отдельные законодательные акты Российской Федерации»",
     "№ 247-ФЗ «О социальных гарантиях"),
    (r"Дисциплинарн\w+ устав\w*", "Дисциплинарный устав",
     "Дисциплинарный устав органов внутренних дел Российской Федерации, утверждённый Указом Президента "
     "Российской Федерации от 14.10.2012 № 1377", "от 14.10.2012 № 1377"),
    (r"Регламент\w* МВД России|п\. \d+ Регламента", "Регламент МВД России",
     "Регламент Министерства внутренних дел Российской Федерации, утверждённый приказом МВД России "
     "от 14.11.2022 № 855", "от 14.11.2022 № 855"),
    (r"КоАП РФ", "КоАП РФ", "Кодекс Российской Федерации об административных правонарушениях",
     "Российской Федерации об административных правонарушениях"),
    (r"Указ\w* № 250", "Указ № 250",
     "Указ Президента Российской Федерации от 01.03.2011 № 250 «Вопросы организации полиции»",
     "№ 250 «Вопросы организации полиции»"),
    (r"Указ\w* № 668", "Указ № 668",
     "Указ Президента Российской Федерации от 23.05.2011 № 668 «Об общественных советах при Министерстве "
     "внутренних дел Российской Федерации и его территориальных органах»", "№ 668 «Об общественных советах"),
    (r"Указ\w* № 1535|от 11\.12\.2010 № 1535", "Указ № 1535",
     "Указ Президента Российской Федерации от 11.12.2010 № 1535 «О дополнительных мерах по обеспечению "
     "правопорядка»", "№ 1535 «О дополнительных мерах"),
    (r"Положени\w+ о координации|Указ\w* № 567|от 18\.04\.1996 № 567", "Положение о координации (Указ № 567)",
     "Положение о координации деятельности правоохранительных органов по борьбе с преступностью, "
     "утверждённое Указом Президента Российской Федерации от 18.04.1996 № 567",
     "о координации деятельности правоохранительных органов по борьбе с преступностью, утв."),
    (r"Концепци[ияю]\b", "Концепция",
     "Концепция общественной безопасности в Российской Федерации, утверждённая Президентом "
     "Российской Федерации 14.11.2013 № Пр-2685", "общественной безопасности в Российской Федерации, утв."),
    (r"Стратеги[ияю]\b", "Стратегия",
     "Стратегия национальной безопасности Российской Федерации, утверждённая Указом Президента "
     "Российской Федерации от 02.07.2021 № 400", "национальной безопасности Российской Федерации, утв."),
    (r"Кодекс\w* этики(?! членов)", "Кодекс этики",
     "Кодекс этики и служебного поведения сотрудников органов внутренних дел Российской Федерации, "
     "утверждённый приказом МВД России от 26.06.2020 № 460",
     "этики и служебного поведения сотрудников органов внутренних дел, утв."),
    (r"Инструкци[ияю]\b|приказ\w* МВД России № 1011|приказ\w* № 1011", "Инструкция (приказ МВД России № 1011)",
     "Инструкция по организации и проведению отчётов должностных лиц территориальных органов МВД России, "
     "утверждённая приказом МВД России от 26.12.2023 № 1011",
     "отчётов должностных лиц территориальных органов МВД России, утв."),
]

TOKEN = re.compile(r"(\*\*|//|__)")
NBSP = "\u00a0"


def typo(text):
    """Неразрывные пробелы в ссылках на нормы, чтобы «ст. 5» не разрывалось по строкам."""
    text = re.sub(r"\b(ст|ч|п|пп|подп|гл)\. (?=[\d«IVX])", lambda m: m.group(1) + "." + NBSP, text)
    text = text.replace("№ ", "№" + NBSP)
    text = re.sub(r"(\d) (г\.|гг\.|часов|часа|дней|суток|лет)", lambda m: m.group(1) + NBSP + m.group(2), text)
    return text


def set_fonts(rpr, size=None):
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in list(rfonts.attrib):
        del rfonts.attrib[attr]
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)
    if size is not None:
        for tag in ("w:sz", "w:szCs"):
            el = rpr.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                rpr.append(el)
            el.set(qn("w:val"), str(int(size * 2)))


def style_fonts(style, size, bold=None, italic=None):
    rpr = style.element.get_or_add_rPr()
    set_fonts(rpr, size)
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic


def para_format(fmt, before=0, after=6, left=0.0, first=0.0, keep=False):
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = 1.0
    fmt.left_indent = Cm(left)
    fmt.first_line_indent = Cm(first)
    fmt.keep_with_next = keep
    fmt.widow_control = True


def border(par, sides, size=8, space=6, color="000000"):
    ppr = par._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        if side not in sides:
            continue
        el = OxmlElement("w:" + side)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), str(space))
        el.set(qn("w:color"), color)
        bdr.append(el)
    ppr.append(bdr)


def add_runs(par, text, base_bold=False, base_italic=False):
    bold = italic = under = False
    for piece in TOKEN.split(typo(text)):
        if piece == "**":
            bold = not bold
        elif piece == "//":
            italic = not italic
        elif piece == "__":
            under = not under
        elif piece:
            run = par.add_run(piece)
            if bold or base_bold:
                run.bold = True
            if italic or base_italic:
                run.italic = True
            if under:
                run.underline = True
    assert not (bold or italic or under), "незакрытая разметка: " + text[:80]


def page_number(section):
    par = section.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(11)


def prepare(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin, sec.right_margin = Cm(2.5), Cm(1.5)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    page_number(sec)

    # Шрифт по умолчанию для всего документа.
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    rpr = defaults.find(qn("w:rPrDefault")).find(qn("w:rPr"))
    set_fonts(rpr, BODY_PT)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    for attr in ("w:val", "w:eastAsia"):
        lang.set(qn(attr), "ru-RU")

    # Одинарный интервал и нулевые отступы по умолчанию; ни один стиль не ссылается на шрифты темы.
    ppr = defaults.find(qn("w:pPrDefault")).find(qn("w:pPr"))
    spacing = ppr.find(qn("w:spacing"))
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "240")
    spacing.set(qn("w:lineRule"), "auto")
    for rfonts in doc.styles.element.iter(qn("w:rFonts")):
        for attr in list(rfonts.attrib):
            del rfonts.attrib[attr]
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), FONT)

    st = doc.styles
    style_fonts(st["Normal"], BODY_PT)
    para_format(st["Normal"].paragraph_format, after=6, first=1.25)
    st["Normal"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    style_fonts(st["Heading 1"], 16, bold=True)
    para_format(st["Heading 1"].paragraph_format, before=0, after=12, keep=True)
    st["Heading 1"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    style_fonts(st["Heading 2"], BODY_PT, bold=True)
    para_format(st["Heading 2"].paragraph_format, before=10, after=6, keep=True)
    st["Heading 2"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    style_fonts(st["Footer"], 11)


def bookmark(par, name, num):
    """Закладка на абзаце: на неё ведут ссылки из содержания."""
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(num))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(num))
    par._p.insert(par._p.index(par._p.get_or_add_pPr()) + 1, start)
    par._p.append(end)


def link_to_bookmark(par, text, name):
    """Текст-ссылка на закладку внутри документа (переход по щелчку с Ctrl)."""
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), name)
    link.set(qn("w:history"), "1")
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = typo(text)
    run.append(t)
    link.append(run)
    par._p.append(link)


def read_lists(code):
    """Перечни вопросов дисциплины: [(подпись, {номер: формулировка})]."""
    res = []
    folder = os.path.join(ROOT, DISCIPLINES[code], "1. Примерный перечень вопросов")
    for spec in LISTS.get(code, ()):
        label, mark, block = spec[0], spec[1], (spec[2] if len(spec) > 2 else 0)
        path = [p for p in sorted(glob.glob(os.path.join(folder, "*.txt")))
                if (os.path.basename(p).startswith(mark[1:]) if mark.startswith("^") else mark in os.path.basename(p))][0]
        blocks, cur = [{}], None
        for line in open(path, encoding="utf-8").read().replace("\r", "").split("\n"):
            m = re.match(r"\s*(\d+)\.\s*(.*)", line)
            if m:
                num = int(m.group(1))
                if num == 1 and cur and cur > 1:      # нумерация началась заново — следующий блок
                    blocks.append({})
                elif num == cur:                       # номер повторён (опечатка в перечне) — следующий по порядку
                    num = cur + 1
                cur = num
                blocks[-1][cur] = m.group(2).strip()
            elif cur and line.strip():
                blocks[-1][cur] += " " + line.strip()
        res.append((label, {k: re.sub(r"\s+", " ", v) for k, v in blocks[block].items()}))
    return res


def read_map(code):
    """map.tsv: номер ответа и по столбцу на каждый перечень — номера вопросов, которые закрывает ответ."""
    path = os.path.join(ROOT, ".github", "answers", code, "map.tsv")
    res = {}
    if not os.path.exists(path):
        return res
    for line in open(path, encoding="utf-8").read().split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        width = len(LISTS.get(code, ())) or 2
        cols = (line.split("\t") + [""] * width)[:width + 1]
        res[int(cols[0])] = [[int(x) for x in c.replace(" ", "").split(",") if x] for c in cols[1:]]
    return res


def covers(code, n):
    """Строка под заголовком ответа: какие вопросы перечней он закрывает."""
    mp = read_map(code).get(n)
    if not mp:
        return ""
    bits = []
    for spec, nums in zip(LISTS[code], mp):
        label = spec[0]
        if nums:
            bits.append("%s — вопрос%s %s" % (label, "ы" if len(nums) > 1 else "", ", ".join(map(str, nums))))
    return "; ".join(bits)


def list_index(doc, code, questions):
    """Указатели: вопрос перечня → номера ответов (со ссылками)."""
    have = {q["n"] for q in questions}
    mp = read_map(code)
    for idx, (label, items) in enumerate(read_lists(code)):
        par = doc.add_paragraph()
        para_format(par.paragraph_format, before=14, after=10, first=0, keep=True)
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run("Указатель: вопросы перечня «%s» и номера ответов" % label).bold = True
        for num in sorted(items):
            answers = [n for n in sorted(mp) if num in mp[n][idx] and n in have]
            par = doc.add_paragraph()
            para_format(par.paragraph_format, after=3, left=1.25, first=-1.25)
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            par.paragraph_format.tab_stops.add_tab_stop(Cm(1.25))
            add_runs(par, "%d.\t%s — " % (num, items[num].rstrip(".")))
            if not answers:
                add_runs(par, "ответа пока нет")
            for k, n in enumerate(answers):
                if k:
                    add_runs(par, ", ")
                link_to_bookmark(par, ("ответ %d" if len(answers) == 1 else "%d") % n if k or len(answers) == 1
                                 else "ответы %d" % n, "q%03d" % n)
            add_runs(par, ".")


def contents(doc, code, questions):
    """Титульная строка и содержание общего документа: перечень вопросов со ссылками на ответы."""
    par = doc.add_paragraph()
    para_format(par.paragraph_format, after=6, first=0)
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run(DISCIPLINES[code])
    run.bold = True
    run.font.size = Pt(16)

    par = doc.add_paragraph()
    para_format(par.paragraph_format, after=18, first=0)
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    nums = [q["n"] for q in questions]
    if nums == list(range(nums[0], nums[-1] + 1)):
        title = "Ответы на вопросы %d–%d" % (nums[0], nums[-1])
    else:
        title = "Ответы на вопросы " + ", ".join(str(n) for n in nums)
    if code in LISTS:
        title = title.replace("Ответы на вопросы", "Ответы")
    run = par.add_run(VARIANTS[code] + ". " + title if code != "adp" else title)
    run.bold = True
    run.font.size = Pt(16)

    if code in INTRO:
        par = doc.add_paragraph()
        para_format(par.paragraph_format, after=14, first=0)
        add_runs(par, INTRO[code])
        for run in par.runs:
            run.font.size = Pt(12)

    par = doc.add_paragraph()
    para_format(par.paragraph_format, after=10, first=0, keep=True)
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run("Содержание").bold = True

    for q in questions:
        par = doc.add_paragraph()
        para_format(par.paragraph_format, after=3, left=1.25, first=-1.25)
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        par.paragraph_format.tab_stops.add_tab_stop(Cm(1.25))
        link_to_bookmark(par, "%d.\t%s" % (q["n"], q["title"]), "q%03d" % q["n"])
        # знак табуляции внутри ссылки
        t = par._p.findall(".//" + qn("w:t"))[-1]
        num, title = t.text.split("\t", 1)
        t.text = num
        tab = OxmlElement("w:tab")
        t.addnext(tab)
        t2 = OxmlElement("w:t")
        t2.set(qn("xml:space"), "preserve")
        t2.text = title
        tab.addnext(t2)

    if code in LISTS:
        list_index(doc, code, questions)

    doc.add_page_break()


def abbr_note(text):
    used = []
    for pat, short, full, mark in ABBR:
        marks = mark if isinstance(mark, tuple) else (mark,)
        if re.search(pat, text) and not any(m in text for m in marks):
            used.append((short, full))
    return "; ".join("**%s** — %s" % (short, full) for short, full in used)


def out_dir(code):
    path = os.path.join(ROOT, DISCIPLINES[code], "3. Ответы на вопросы", VARIANTS[code])
    os.makedirs(path, exist_ok=True)
    return path


def last_question(code):
    nums = []
    for path in glob.glob(os.path.join(ROOT, ".github", "answers", code, "*.txt")):
        nums += [int(n) for n in re.findall(r"(?m)^# Вопрос (\d+)\. ", open(path, encoding="utf-8").read())]
    return max(nums)


def build(code, first, last, one=False, sample=False):
    src = sorted(glob.glob(os.path.join(ROOT, ".github", "answers", code, "*.txt")))
    lines = []
    for path in src:
        lines += open(path, encoding="utf-8").read().split("\n")

    questions, cur = [], None
    for line in lines:
        m = re.match(r"# Вопрос (\d+)\. (.*)", line)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "body": []}
            questions.append(cur)
        elif cur is not None:
            cur["body"].append(line)
    questions = sorted((q for q in questions if first <= q["n"] <= last), key=lambda q: q["n"])
    if sample:
        one = True
        assert questions and len({q["n"] for q in questions}) == len(questions)
    else:
        assert [q["n"] for q in questions] == list(range(first, last + 1)), [q["n"] for q in questions]

    doc = Document()
    prepare(doc)
    doc.core_properties.title = "%s. Ответы на вопросы %d–%d" % (DISCIPLINES[code], first, last)
    doc.core_properties.language = "ru-RU"
    doc.core_properties.author = ""

    if one:
        contents(doc, code, questions)

    for q in questions:
        head = doc.add_paragraph(style="Heading 1")
        add_runs(head, ("Ответ %d. %s" if code in LISTS else "Вопрос %d. %s") % (q["n"], q["title"]))
        if one:
            bookmark(head, "q%03d" % q["n"], q["n"])

        cov = covers(code, q["n"]) if code in LISTS else ""
        if cov:
            par = doc.add_paragraph()
            para_format(par.paragraph_format, after=10, first=0)
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(par, "//" + cov[0].upper() + cov[1:] + "//")
            for run in par.runs:
                run.font.size = Pt(11)

        note = abbr_note("\n".join(q["body"])) if code.startswith("adp") else ""
        if note:
            par = doc.add_paragraph()
            para_format(par.paragraph_format, after=10, first=0)
            add_runs(par, "//Сокращения в ответе:// " + note + ".")
            for run in par.runs:
                run.font.size = Pt(11)

        for line in q["body"]:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("## "):
                add_runs(doc.add_paragraph(style="Heading 2"), line[3:])
            elif line.startswith("> "):
                par = doc.add_paragraph()
                para_format(par.paragraph_format, before=2, after=8, left=0.75, first=0)
                border(par, ("left",), size=18, space=8)
                add_runs(par, line[2:])
            elif line.startswith("!! "):
                par = doc.add_paragraph()
                para_format(par.paragraph_format, before=8, after=6, left=0.2, first=0)
                par.paragraph_format.right_indent = Cm(0.2)
                border(par, ("top", "left", "bottom", "right"), size=8, space=5)
                add_runs(par, line[3:])
            elif line.startswith("- "):
                par = doc.add_paragraph()
                para_format(par.paragraph_format, after=3, left=1.25, first=-0.6)
                par.paragraph_format.tab_stops.add_tab_stop(Cm(1.25))
                add_runs(par, "–\t" + line[2:])
            elif re.match(r" {2,}- ", line):
                par = doc.add_paragraph()
                para_format(par.paragraph_format, after=3, left=2.0, first=-0.6)
                par.paragraph_format.tab_stops.add_tab_stop(Cm(2.0))
                add_runs(par, "–\t" + line.lstrip()[2:])
            else:
                assert not line.startswith(("#", ">", "!", " ")), line[:60]
                add_runs(doc.add_paragraph(), line)

        for _ in range(EMPTY_AFTER_QUESTION):
            par = doc.add_paragraph()
            para_format(par.paragraph_format, after=0, first=0)

    if sample:
        name = "Пробные ответы (вопросы %s).docx" % ", ".join(str(q["n"]) for q in questions)
    else:
        name = ("Все ответы %03d–%03d (один файл).docx" if one else "Ответы на вопросы %03d–%03d.docx") % (first, last)
    out = os.path.join(out_dir(code), name)
    doc.save(out)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    code = args[0]
    if "--sample" in flags:
        print(build(code, 1, 10 ** 6, sample=True))
    elif "--all" in flags:
        total = last_question(code)
        for start in range(1, total + 1, PER_FILE):
            print(build(code, start, min(start + PER_FILE - 1, total)))
        print(build(code, 1, total, one=True))
    else:
        print(build(code, int(args[1]), int(args[2]), one="--one" in flags))
