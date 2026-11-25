#!/usr/bin/env python3
"""График подготовки к зачётам и экзаменам: расчёт по дням и документ Word.

Запуск:  python .github/answers/tools/build_schedule.py
Нужен пакет python-docx. Документ сохраняется в корень репозитория.

Нагрузка выравнивается по числу слов в ответах (q*.txt), время считается
при 100 словах в минуту. Оформление: шрифт PT Astra Serif, поля 30/15/20/20 мм,
основной текст 14 пт через 1,5 интервала, абзацный отступ 1,25 см,
таблицы 12 пт, подписи «Таблица N – …» над таблицей (ГОСТ 7.32-2017).
"""
import datetime as D
import glob
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[3]
ANS = ROOT / ".github" / "answers"
OUT = ROOT / "График подготовки к зачётам и экзаменам.docx"

FONT = "PT Astra Serif"
NBSP = "\u00a0"
WPM = 100                       # слов в минуту
N = {"adp": 149, "adp2": 149, "ugp": 117, "upp": 108, "tsp": 87, "tp": 70, "krim": 44, "gpp": 52}
ADP2_EARLY, UGP_EARLY = 32, 74  # где делятся вторые проходы в январе


# ───────────────────────── расчёт графика ─────────────────────────

def words():
    out = {}
    for code in N:
        d = {}
        for f in sorted(glob.glob(str(ANS / code / "q*.txt"))):
            parts = re.split(r"(?m)^# Вопрос (\d+)\.", Path(f).read_text(encoding="utf-8"))
            for i in range(1, len(parts), 2):
                n = int(parts[i])
                d[n] = d.get(n, 0) + len(parts[i + 1].split())
        assert sorted(d) == list(range(1, N[code] + 1)), code
        out[code] = d
    return out


W = words()


def day(s):
    dd, mm = s.split(".")
    return D.date(2026 if int(mm) > 6 else 2027, int(mm), int(dd))


def rng(a, b):
    out, x = [], day(a)
    while x <= day(b):
        out.append(x)
        x += D.timedelta(1)
    return out


EXAMS = [  # дата, дисциплина (родительный падеж для «по …»), форма, читается ли после сдачи
    (day("18.12"), "Трудовое право", "трудовому праву", "зачёт", True),
    (day("24.12"), "Гражданско-процессуальное право (ГПП)", "ГПП", "зачёт", True),
    (day("26.12"), "Криминалистика", "криминалистике", "зачёт", True),
    (day("30.12"), "Тактико-специальная подготовка (ТСП)", "ТСП", "зачёт", False),
    (day("12.01"), "Уголовно-процессуальное право (УПП)", "УПП", "экзамен", True),
    (day("15.01"), "Уголовное право", "уголовному праву", "экзамен", True),
    (day("19.01"), "Административная деятельность полиции (АДП)", "АДП", "экзамен", False),
]
HALF = {e[0] for e in EXAMS if e[4]}
REST = set(rng("31.12", "04.01"))


def wt(x):
    return 0.5 if x in HALF else (2 if x.weekday() == 6 else 1)


def blk(c, p, a, b):
    return [(c, p, q, W[c][q]) for q in range(a, b + 1)]


def tot(qs):
    return sum(q[3] for q in qs)


def build_plan():
    plan = {}

    def fill(days, caps, qs):
        t, s, bounds, c = tot(qs), sum(caps), [], 0
        for k in caps:
            c += k
            bounds.append(t * c / s)
        cum = i = 0
        for q in qs:
            mid = cum + q[3] / 2
            cum += q[3]
            while mid > bounds[i] + 1e-9:
                i += 1
            plan.setdefault(days[i], []).append(q)

    def load(x):
        return tot(plan.get(x, []))

    # до Нового года
    stream = blk("adp", 1, 1, 149) + blk("upp", 1, 1, 108) + blk("ugp", 1, 1, 117) + blk("adp2", 1, 1, 149)
    krim = blk("krim", 1, 1, 44) + blk("krim", 2, 1, 44)
    gpp = blk("gpp", 1, 1, 52)
    sdays = rng("26.11", "15.12") + rng("18.12", "26.12")
    rate = (tot(stream) + tot(krim) + tot(gpp)) / sum(wt(x) for x in sdays)
    rest = tot(krim) - 1.5 * rate           # 24 и 25 декабря — только криминалистика
    fill([day("19.12"), day("20.12"), day("21.12"), day("24.12"), day("25.12")],
         [rest / 4, rest / 2, rest / 4, 0.5 * rate, rate], krim)
    fill(rng("22.12", "23.12"), [tot(gpp) - rate, rate], gpp)   # 23 декабря — только ГПП
    fill(rng("16.12", "17.12"), [1, 1], blk("tp", 1, 1, 70))
    fill(rng("27.12", "29.12"), [2, 1, 1], blk("tsp", 1, 1, 87) + blk("tsp", 2, 1, 87))
    caps = [max(rate * wt(x) - load(x), 0) for x in sdays]
    keep = [(x, c) for x, c in zip(sdays, caps) if c > 500]
    fill([x for x, _ in keep], [c for _, c in keep], stream)
    # январь: только вторые проходы
    fill(rng("05.01", "09.01"), [1] * 5, blk("adp2", 2, 1, ADP2_EARLY) + blk("ugp", 2, 1, UGP_EARLY))
    fill(rng("10.01", "11.01"), [2, 1], blk("upp", 2, 1, 108))
    fill(rng("12.01", "14.01"), [0.5, 1, 1], blk("ugp", 2, UGP_EARLY + 1, 117))
    fill(rng("15.01", "18.01"), [0.5, 1, 2, 1], blk("adp2", 2, ADP2_EARLY + 1, 149))

    first = {"krim": 0, "gpp": 0, "tp": 0, "tsp": 0}
    for x in plan:
        plan[x].sort(key=lambda q: first.get(q[0], 1))
    seen = {}
    for x in sorted(plan):
        for c, p, q, _ in plan[x]:
            seen.setdefault((c, p), []).append(q)
    assert len(seen) == 13 and all(v == list(range(1, N[k[0]] + 1)) for k, v in seen.items())
    assert not any(x in REST or x in (day("30.12"), day("19.01")) for x in plan)
    return plan


PLAN = build_plan()

NAME = {
    ("adp", 1): "АДП, большой вариант", ("adp2", 1): "АДП, малый вариант, 1-й проход",
    ("adp2", 2): "АДП, малый вариант, 2-й проход", ("ugp", 1): "Уголовное право, 1-й проход",
    ("ugp", 2): "Уголовное право, 2-й проход", ("upp", 1): "УПП, 1-й проход", ("upp", 2): "УПП, 2-й проход",
    ("tp", 1): "Трудовое право", ("gpp", 1): "ГПП", ("krim", 1): "Криминалистика, 1-й проход",
    ("krim", 2): "Криминалистика, 2-й проход", ("tsp", 1): "ТСП, 1-й проход", ("tsp", 2): "ТСП, 2-й проход",
}
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTH = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
         "октября", "ноября", "декабря"]


def items(x):
    out, cur = [], None
    for c, p, q, w in PLAN[x]:
        if cur and cur[0] == (c, p) and cur[2] == q - 1:
            cur[2] = q
            cur[3] += w
        else:
            cur = [(c, p), q, q, w]
            out.append(cur)
    return out


def mins(x):
    """Расчётное время дня, округлённое до 5 минут."""
    return round(tot(PLAN[x]) / WPM / 5) * 5


def hm(m):
    m = int(round(m))
    return f"{m // 60}~ч {m % 60:02d}~мин"


def dm(x):
    return f"{x.day:02d}.{x.month:02d}"


def dmy(x):
    return f"{x.day:02d}.{x.month:02d}.{x.year}"


def long_date(x):
    return f"{x.day}~{MONTH[x.month]} {x.year}~г."


def spans(dates):
    """Список дат → «13.12–15.12, 18.12–22.12, 26.12»."""
    out, start, prev = [], None, None
    for x in sorted(dates):
        if prev is not None and x - prev == D.timedelta(1):
            prev = x
            continue
        if start is not None:
            out.append((start, prev))
        start = prev = x
    out.append((start, prev))
    return ", ".join(dm(a) if a == b else f"{dm(a)}–{dm(b)}" for a, b in out)


def num(n):
    return f"{n:,}".replace(",", "~")


# ───────────────────────── оформление ─────────────────────────

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


def style(st, size, bold=False):
    set_fonts(st.element.get_or_add_rPr(), size)
    st.font.name = FONT
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.italic = False
    st.font.color.rgb = RGBColor(0, 0, 0)


def setup(doc):
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin, sec.right_margin = Cm(3), Cm(1.5)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    sec.header_distance = sec.footer_distance = Cm(1.25)
    sec.different_first_page_header_footer = True      # первая страница без номера

    defaults = doc.styles.element.find(qn("w:docDefaults"))
    rpr = defaults.find(qn("w:rPrDefault")).find(qn("w:rPr"))
    for old in rpr.findall(qn("w:lang")):                  # порядок в rPr: rFonts, sz, szCs, lang
        rpr.remove(old)
    set_fonts(rpr, 14)
    lang = OxmlElement("w:lang")
    rpr.append(lang)
    for attr in ("w:val", "w:eastAsia", "w:bidi"):
        lang.set(qn(attr), "ru-RU" if attr != "w:bidi" else "ar-SA")
    for rfonts in doc.styles.element.iter(qn("w:rFonts")):
        for attr in list(rfonts.attrib):
            del rfonts.attrib[attr]
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), FONT)

    st = doc.styles
    style(st["Normal"], 14)
    fmt = st["Normal"].paragraph_format
    fmt.space_before = fmt.space_after = Pt(0)
    fmt.line_spacing = 1.5
    fmt.widow_control = True

    style(st["Heading 1"], 14, bold=True)
    fmt = st["Heading 1"].paragraph_format
    fmt.space_before, fmt.space_after = Pt(18), Pt(12)
    fmt.line_spacing = 1.5
    fmt.first_line_indent = Cm(1.25)
    fmt.left_indent = Cm(0)
    fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fmt.keep_with_next = True

    style(st["Footer"], 12)
    par = sec.footer.paragraphs[0]
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

    props = doc.core_properties
    props.title = "График подготовки к зачётам и экзаменам"
    props.subject = "26 ноября 2026 г. – 19 января 2027 г."
    props.author = ""
    props.language = "ru-RU"


def runs(par, text, bold=False):
    """«**…**» — полужирный, «~» — неразрывный пробел."""
    for i, part in enumerate(text.split("**")):
        if part:
            r = par.add_run(part.replace("~", NBSP))
            r.bold = bold or i % 2 == 1


class Doc:
    def __init__(self):
        self.doc = Document()
        setup(self.doc)
        self.after_table = False
        self.tables = 0

    def _gap(self, par):
        if self.after_table:
            par.paragraph_format.space_before = Pt(12)
            self.after_table = False

    def title(self, lines):
        for i, line in enumerate(lines):
            par = self.doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.keep_with_next = True
            runs(par, line, bold=True)
        par.paragraph_format.space_after = Pt(12)

    def h(self, text):
        par = self.doc.add_paragraph(style="Heading 1")
        runs(par, text, bold=True)
        self.after_table = False

    def p(self, text):
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        par.paragraph_format.first_line_indent = Cm(1.25)
        self._gap(par)
        runs(par, text)
        return par

    def ul(self, lines):
        for i, line in enumerate(lines):
            end = "." if i == len(lines) - 1 else ";"
            self.p("–~" + line + end)

    def table(self, caption, widths, header, rows, aligns, total=None, note=None):
        """rows: список строк; ячейка — строка или список строк (абзацы)."""
        self.tables += 1
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cap.paragraph_format.keep_with_next = True
        cap.paragraph_format.line_spacing = 1.0
        cap.paragraph_format.space_after = Pt(6)
        cap.paragraph_format.space_before = Pt(12)
        self.after_table = False
        runs(cap, f"Таблица~{self.tables}~–~{caption}")

        body = [header] + rows + ([total] if total else [])
        tbl = self.doc.add_table(rows=len(body), cols=len(widths))
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        tblw = tbl._tbl.tblPr.find(qn("w:tblW"))
        tblw.set(qn("w:type"), "dxa")
        tblw.set(qn("w:w"), str(round(sum(widths) * 567)))
        for col, width in zip(tbl.columns, widths):
            col.width = Cm(width)
        for r, cells in enumerate(body):
            row = tbl.rows[r]
            trpr = row._tr.get_or_add_trPr()
            trpr.append(OxmlElement("w:cantSplit"))
            if r == 0:
                trpr.append(OxmlElement("w:tblHeader"))
            is_head, is_total = r == 0, bool(total) and r == len(body) - 1
            for c, content in enumerate(cells):
                cell = row.cells[c]
                cell.width = Cm(widths[c])
                if is_head or is_total:                     # порядок в tcPr: tcW, shd, vAlign
                    shd = OxmlElement("w:shd")
                    for k, v in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", "F2F2F2")):
                        shd.set(qn(k), v)
                    cell._tc.get_or_add_tcPr().append(shd)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                paras = content if isinstance(content, list) else [content]
                for i, text in enumerate(paras):
                    par = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
                    fmt = par.paragraph_format
                    fmt.line_spacing = 1.0
                    fmt.space_before = fmt.space_after = Pt(2)
                    fmt.keep_with_next = r < len(body) - 1 or bool(note)   # таблица не рвётся между страницами
                    par.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_head else aligns[c]
                    runs(par, text, bold=is_head or is_total)
                    for run in par.runs:
                        run.font.size = Pt(12)
        if note:
            par = self.doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            par.paragraph_format.first_line_indent = Cm(1.25)
            par.paragraph_format.space_before = Pt(6)
            par.paragraph_format.line_spacing = 1.0
            runs(par, "Примечание~–~" + note)
            for run in par.runs:
                run.font.size = Pt(12)
        self.after_table = True
        return tbl


L, C = WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER


# ───────────────────────── содержание документа ─────────────────────────

def what_cell(x):
    """Текст ячейки «Что читать» для дня графика."""
    out = []
    exam = next((e for e in EXAMS if e[0] == x), None)
    if exam:
        out.append(f"**{exam[3].capitalize()} по {exam[2]}.** После сдачи:")
    for k, a, b, _ in items(x):
        out.append(f"{NAME[k].replace('й проход', 'й~проход')}: вопросы~{a}–{b}")
    return out


def count_cell(x):
    its = items(x)
    n = [b - a + 1 for _, a, b, _ in its]
    return [str(sum(n))] + ([f"({'~+~'.join(map(str, n))})"] if len(n) > 1 else [])


def week_tables(doc):
    weeks = {}
    for x in rng("26.11", "19.01"):
        weeks.setdefault(x - D.timedelta(x.weekday()), []).append(x)
    widths = [2.2, 6.7, 2.6, 2.8, 2.2]
    header = ["Дата", "Что читать", "Вопросов", "Время", "Отметка"]
    for i, (_, days) in enumerate(sorted(weeks.items()), 1):
        rows, q, m = [], 0, 0
        for x in days:
            date = f"{dm(x)}, {WD[x.weekday()]}".replace(" ", "~")
            if x.weekday() == 6:
                date = f"**{date}**"
            if x in PLAN:
                n = sum(b - a + 1 for _, a, b, _ in items(x))
                q += n
                m += mins(x)
                rows.append([date, what_cell(x), count_cell(x), hm(mins(x)), ""])
            elif x in REST:
                rows.append([date, "Отдых, чтения нет", "–", "–", ""])
            else:
                exam = next(e for e in EXAMS if e[0] == x)
                rows.append([date, f"**{exam[3].capitalize()} по {exam[2]}.** Чтения нет", "–", "–", ""])
        a, b = days[0], days[-1]
        if a.month == b.month:
            period = f"{a.day}–{b.day}~{MONTH[a.month]} {b.year}~г."
        elif a.year == b.year:
            period = f"{a.day}~{MONTH[a.month]}~– {b.day}~{MONTH[b.month]} {b.year}~г."
        else:
            period = f"{long_date(a)}~– {long_date(b)}"
        tbl = doc.table(f"Неделя~{i}: {period}", widths, header, rows, [C, L, C, C, C],
                        total=["Итого за неделю", "", str(q), hm(m), ""])
        last = tbl.rows[-1]
        last.cells[0].merge(last.cells[1])
        last.cells[0].paragraphs[0].alignment = L


def by_days(pred):
    return [x for x in sorted(PLAN) if pred(x)]


def span_minutes(days):
    v = [mins(x) for x in days]
    return f"{hm(min(v))}~– {hm(max(v))}" if v else "–"


def build():
    doc = Doc()
    total_words = sum(tot(v) for v in PLAN.values())
    workdays = by_days(lambda x: x.weekday() != 6 and x not in HALF)
    sundays = by_days(lambda x: x.weekday() == 6)
    avg_work = sum(tot(PLAN[x]) for x in workdays) / len(workdays) / WPM
    avg_sun = sum(tot(PLAN[x]) for x in sundays) / len(sundays) / WPM
    all_days = rng("26.11", "19.01")
    mln = f"{total_words / 1e6:.1f}".replace(".", ",")

    doc.title(["ГРАФИК", "подготовки к зачётам и экзаменам",
               "на период с~26~ноября 2026~г. по~19~января 2027~г."])

    # 1
    doc.h("1~Общие сведения")
    doc.p("Настоящий график определяет, какие вопросы и по какой дисциплине читать в каждый день "
          "с~26~ноября 2026~г. по~18~января 2027~г. Читаются готовые ответы на вопросы: по каждой "
          "дисциплине это один файл «Все ответы… (один файл)». Номера вопросов в графике совпадают "
          "с~номерами ответов в~этих файлах.")
    doc.p(f"Период графика~– {len(all_days)}~дней: {len(PLAN)}~дней чтения, 5~дней отдыха "
          f"(с~31~декабря по~4~января) и 2~дня сдачи без чтения (30~декабря и 19~января). "
          f"Общий объём чтения~– около {mln}~млн слов, расчётное время~– около "
          f"{round(total_words / WPM / 60)}~часов.")
    doc.p("В графике применены сокращения: АДП~– административная деятельность полиции; ГПП~– "
          "гражданско-процессуальное право; ТСП~– тактико-специальная подготовка; УПП~– "
          "уголовно-процессуальное право.")
    doc.p("Даты зачётов и экзаменов приведены в таблице~1.")

    last_days = {}
    for e in EXAMS:
        codes = {"Трудовое право": ["tp"], "Криминалистика": ["krim"], "Уголовное право": ["ugp"]}.get(e[1])
        if codes is None:
            codes = {"ГПП": ["gpp"], "ТСП": ["tsp"], "УПП": ["upp"], "АДП": ["adp2"]}[e[2]]
        last_pass = 2 if (codes[0], 2) in NAME else 1
        ds = [x for x in PLAN if any(q[0] == codes[0] and q[1] == last_pass for q in PLAN[x])]
        last_days[e[0]] = spans(ds)
    doc.table("Даты зачётов и экзаменов", [3.3, 6.4, 2.3, 4.5],
              ["Дата", "Дисциплина", "Форма", "Дни последнего прохода"],
              [[f"{dmy(e[0])},~{WD[e[0].weekday()]}", e[1], e[3], last_days[e[0]]] for e in EXAMS],
              [C, L, C, C])

    # 2
    doc.h("2~Исходные условия")
    doc.p("График составлен при следующих условиях:")
    doc.ul([
        "чтение начинается 26~ноября 2026~г. (четверг)",
        "дни без чтения: 30 и 31~декабря 2026~г., 1, 2, 3 и 4~января 2027~г., а также 19~января 2027~г. "
        "(день экзамена по АДП)",
        "в воскресенье читается вдвое больше, чем в будний день",
        "в день зачёта или экзамена читается половина обычной нормы, после сдачи",
        "на трудовое право и ГПП отведено по два дня перед зачётом, на криминалистику~– пять дней",
        "АДП читается три раза: один раз большой вариант (вариант~1, подробные ответы) и два раза "
        "малый вариант (вариант~2, сокращённые ответы)",
        "криминалистика, ТСП, УПП и уголовное право читаются по два раза, трудовое право и ГПП~– "
        "по одному разу",
        "вторые проходы по УПП, уголовному праву и малому варианту АДП целиком приходятся на январь",
        f"время рассчитано при скорости чтения {WPM}~слов в минуту",
    ])
    doc.p("Объём материала и число проходов приведены в таблице~2.")

    rows, tw, tm = [], 0, 0
    for label, code, passes in (
            ("АДП, большой вариант", "adp", 1), ("АДП, малый вариант", "adp2", 2),
            ("Уголовное право", "ugp", 2), ("УПП", "upp", 2), ("ТСП", "tsp", 2),
            ("Криминалистика", "krim", 2), ("Трудовое право", "tp", 1), ("ГПП", "gpp", 1)):
        w = sum(W[code].values())
        tw += w * passes
        tm += w * passes / WPM
        rows.append([label, str(N[code]), num(w), hm(w / WPM), str(passes), hm(w * passes / WPM)])
    doc.table("Объём материала и число проходов", [3.7, 2.4, 2.3, 2.7, 2.4, 3.0],
              ["Дисциплина", "Вопросов", "Слов", "Один проход", "Проходов", "Всего"],
              rows, [L, C, C, C, C, C], total=["Итого", "–", num(tw), "–", "–", hm(tm)],
              note="слова подсчитаны по тексту ответов без оглавления; в графе «Итого» "
                   "число слов указано с~учётом числа проходов.")

    # 3
    doc.h("3~Как пользоваться графиком")
    doc.p("График по дням приведён в разделе~5: на каждую неделю составлена отдельная таблица. "
          "В~строке дня указаны дисциплина, номер прохода, номера вопросов, число вопросов и расчётное "
          "время чтения. В~графе «Отметка» ставится отметка о~выполнении.")
    doc.p("Проход~– это одно полное чтение файла от первого вопроса до последнего. Запись "
          "«УПП, 2-й~проход: вопросы~1–80» означает, что в этот день читаются ответы на вопросы "
          "с~1-го по~80-й во второй раз.")
    doc.p("Число вопросов по дням разное, потому что нагрузка выровнена по объёму текста, а не по "
          "числу вопросов: ответы различаются по длине. Ориентироваться следует на номера вопросов, "
          "а время служит для планирования дня.")
    doc.p("Если в день указаны две дисциплины, первой читается та, что стоит в строке первой. "
          "В~день зачёта или экзамена указанные вопросы читаются после сдачи.")
    doc.p("Если норма дня не выполнена, непрочитанные вопросы рекомендуется разделить поровну "
          "между двумя-тремя следующими днями и не менять порядок вопросов. Отставание по дисциплине "
          "следует закрыть до зачёта или экзамена по ней.")
    doc.p(f"Время в графике округлено до 5~минут. В~среднем на будний день приходится {hm(avg_work)}, "
          f"на воскресенье~– {hm(avg_sun)}. При другой скорости чтения время меняется "
          "пропорционально (таблица~3).")
    doc.table("Расчётное время чтения при разной скорости",
              [4.5, 4.0, 4.0, 4.0],
              ["Скорость чтения", "Будний день, в~среднем", "Воскресенье, в~среднем", "Весь график"],
              [[f"{s}~слов в~минуту", hm(avg_work * WPM / s), hm(avg_sun * WPM / s),
                f"{round(total_words / s / 60)}~ч"] for s in (100, 120, 150)],
              [C, C, C, C])

    # 4
    doc.h("4~Общая схема подготовки")
    doc.p("Подготовка разделена на три этапа с~перерывом на отдых (таблица~4). До 15~декабря идёт "
          "первое чтение материала к экзаменам, с~16 по~29~декабря~– подготовка к зачётам, "
          "с~5 по~18~января~– вторые проходы перед экзаменами.")

    def stage(a, b):
        ds = set(rng(a, b))
        return (span_minutes([x for x in workdays if x in ds]), span_minutes([x for x in sundays if x in ds]))

    def when(code, p):
        return spans([x for x in PLAN if any(q[0] == code and q[1] == p for q in PLAN[x])])

    s1, s2, s3 = stage("26.11", "15.12"), stage("16.12", "29.12"), stage("05.01", "18.01")
    doc.table("Этапы подготовки", [3.0, 7.7, 2.9, 2.9],
              ["Период", "Что читается", "Будний день", "Воскресенье"],
              [["26.11–15.12",
                ["Первое чтение материала к экзаменам:",
                 f"АДП, большой вариант ({when('adp', 1)});",
                 f"УПП, 1-й~проход ({when('upp', 1)});",
                 f"уголовное право, 1-й~проход ({when('ugp', 1)});",
                 "начало 1-го~прохода малого варианта АДП"], s1[0], s1[1]],
               ["16.12–29.12",
                ["Подготовка к зачётам:",
                 f"трудовое право ({when('tp', 1)});",
                 f"криминалистика ({spans([x for x in PLAN if any(q[0] == 'krim' for q in PLAN[x])])});",
                 f"ГПП ({when('gpp', 1)});",
                 f"ТСП ({spans([x for x in PLAN if any(q[0] == 'tsp' for q in PLAN[x])])});",
                 "окончание 1-го~прохода малого варианта АДП"], s2[0], s2[1]],
               ["30.12–04.01", "Зачёт по ТСП 30~декабря; отдых с~31~декабря по~4~января", "–", "–"],
               ["05.01–18.01",
                ["Вторые проходы перед экзаменами:",
                 f"АДП, малый вариант ({when('adp2', 2)});",
                 f"уголовное право ({when('ugp', 2)});",
                 f"УПП ({when('upp', 2)})"], s3[0], s3[1]]],
              [C, L, C, C],
              note="в графах «Будний день» и «Воскресенье» указано наименьшее и наибольшее расчётное "
                   "время; дни зачётов и экзаменов (половина нормы) в~расчёт не включены.")
    doc.p("Дни, в которые читается каждая дисциплина, приведены в таблице~5.")
    rows = []
    for k in [("adp", 1), ("adp2", 1), ("adp2", 2), ("ugp", 1), ("ugp", 2), ("upp", 1), ("upp", 2),
              ("tp", 1), ("krim", 1), ("krim", 2), ("gpp", 1), ("tsp", 1), ("tsp", 2)]:
        ds = [x for x in PLAN if any(q[0] == k[0] and q[1] == k[1] for q in PLAN[x])]
        rows.append([NAME[k].replace("й проход", "й~проход"), str(N[k[0]]), when(*k), str(len(ds))])
    doc.table("Дни чтения по дисциплинам и проходам", [6.3, 2.5, 5.9, 1.8],
              ["Дисциплина, проход", "Вопросов", "Дни чтения", "Дней"], rows, [L, C, C, C])

    # 5
    doc.h("5~График по дням")
    doc.p("В таблицах~6–14 приведён график на каждый день. Воскресенья, в которые норма двойная, "
          "выделены полужирным шрифтом в графе «Дата»; "
          "сокращения дней недели: пн, вт, ср, чт, пт, сб, вс. В~графе «Вопросов» в скобках указано число "
          "вопросов по каждой дисциплине, если в день читаются две дисциплины или два прохода.")
    week_tables(doc)
    assert doc.tables == 14, doc.tables

    # 6
    doc.h("6~Пояснения к графику")
    doc.p("При составлении графика приняты следующие решения:")
    doc.ul([
        "пять дней криминалистики~– это 19, 20, 21, 24 и 25~декабря: 22 и 23~декабря отведены ГПП, "
        "зачёт по которому проходит раньше",
        "19, 20, 21 и 22~декабря вместе с~криминалистикой и ГПП читается малый вариант АДП: без этого "
        "дни перед зачётами были бы на полтора часа легче, а остальные будни~– тяжелее",
        "накануне каждого зачёта читается только дисциплина этого зачёта: 17~декабря~– трудовое право, "
        "23~декабря~– ГПП, 25~декабря~– криминалистика, 28 и 29~декабря~– ТСП",
        "первый проход по ТСП целиком приходится на воскресенье 27~декабря, второй~– на 28 и 29~декабря",
        f"второй проход малого варианта АДП начинается 5 и 6~января (вопросы~1–{ADP2_EARLY}) и "
        f"продолжается с~15 по~18~января (вопросы~{ADP2_EARLY + 1}–149): иначе на 16 и 18~января "
        "пришлось бы по 5,5~часа, а на воскресенье 17~января~– 11~часов",
        f"второй проход по уголовному праву идёт в два приёма: вопросы~1–{UGP_EARLY}~– с~6 по~9~января, "
        f"вопросы~{UGP_EARLY + 1}–117~– с~12 по~14~января, непосредственно перед экзаменом; между ними, "
        "10 и 11~января, читается УПП",
        "два дня трудового права (16 и 17~декабря)~– самые загруженные будни графика, поскольку "
        "весь файл читается за два дня",
    ])

    # 7
    doc.h("7~Возможности снижения дневной нормы")
    doc.p("Общий объём чтения неизменен, поэтому перестановкой вопросов между днями снизить норму "
          "буднего дня нельзя. Норма снижается только при увеличении числа дней чтения:")
    doc.ul([
        "если начать чтение 19~ноября, норма буднего дня до Нового года составит около 3~ч 40~мин; "
        "если начать 16~ноября~– около 3~ч 30~мин; на январь это не влияет",
        "если читать 3 и 4~января, норма буднего дня в январе составит около 3~ч 35~мин",
    ])
    doc.p("В обоих случаях график по дням подлежит пересчёту.")

    doc.doc.save(OUT)
    print(OUT.name, "таблиц:", doc.tables)


if __name__ == "__main__":
    build()
