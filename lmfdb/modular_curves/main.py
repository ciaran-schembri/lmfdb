# -*- coding: utf-8 -*-

import re
from lmfdb import db

from flask import render_template, url_for, request, redirect, abort

from sage.all import ZZ

from lmfdb.utils import (
    SearchArray,
    TextBox,
    TextBoxWithSelect,
    
    SelectBox,
    SneakyTextBox,
    YesNoBox,
    YesNoMaybeBox,
    CountBox,
    redirect_no_cache,
    display_knowl,
    flash_error,
    search_wrap,
    to_dict,
    parse_ints,
    parse_noop,
    parse_bool,
    parse_floats,
    parse_interval,
    parse_element_of,
    parse_bool_unknown,
    parse_nf_string,
    parse_nf_jinv,
    integer_divisors,
    StatsDisplay,
    Downloader,
    comma,
    proportioners,
    totaler,
)
from lmfdb.utils.interesting import interesting_knowls
from lmfdb.utils.search_columns import (
    SearchColumns, MathCol, FloatCol, CheckCol, LinkCol, ProcessedCol, MultiProcessedCol,
)
from lmfdb.utils.search_parsing import search_parser
from lmfdb.api import datapage
from lmfdb.backend.encoding import Json

from lmfdb.number_fields.number_field import field_pretty
from lmfdb.number_fields.web_number_field import nf_display_knowl
from lmfdb.modular_curves import modcurve_page
from lmfdb.modular_curves.web_curve import (
    WebModCurve, get_bread, canonicalize_name, name_to_latex, factored_conductor,
    formatted_dims, url_for_EC_label, url_for_ECNF_label, showj_nf,
)
from string import ascii_lowercase

LABEL_RE = re.compile(r"\d+\.\d+\.\d+\.\d+")
CP_LABEL_RE = re.compile(r"\d+[A-Z]\d+")
SZ_LABEL_RE = re.compile(r"\d+[A-Z]\d+-\d+[a-z]")
RZB_LABEL_RE = re.compile(r"X\d+")
S_LABEL_RE = re.compile(r"\d+(G|B|Cs|Cn|Ns|Nn|A4|S4|A5)(\.\d+){0,3}")
NAME_RE = re.compile(r"X_?(0|1|NS|NS\^?\+|SP|SP\^?\+|S4)?\(\d+\)")

def learnmore_list():
    return [('Source and acknowledgments', url_for(".how_computed_page")),
            ('Completeness of the data', url_for(".completeness_page")),
            ('Reliability of the data', url_for(".reliability_page")),
            ('Modular curve labels', url_for(".labels_page"))]

# Return the learnmore list with the matchstring entry removed
def learnmore_list_remove(matchstring):
    return [t for t in learnmore_list() if t[0].find(matchstring) < 0]

@modcurve_page.route("/")
def index():
    return redirect(url_for(".index_Q", **request.args))

@modcurve_page.route("/Q/")
def index_Q():
    info = to_dict(request.args, search_array=ModCurveSearchArray())
    if len(info) > 1:
        return modcurve_search(info)
    title = r"Modular curves over $\Q$"
    info["level_list"] = ["1-4", "5-8", "9-12", "13-16", "17-23", "24-"]
    info["genus_list"] = ["0", "1", "2", "3", "4-6", "7-20", "21-100", "101-"]
    info["rank_list"] = ["0", "1", "2", "3", "4-6", "7-20", "21-100", "101-"]
    info["stats"] = ModCurve_stats()
    return render_template(
        "modcurve_browse.html",
        info=info,
        title=title,
        bread=get_bread(),
        learnmore=learnmore_list(),
    )

@modcurve_page.route("/Q/random/")
@redirect_no_cache
def random_curve():
    label = db.gps_gl2zhat_test.random()
    return url_for_modcurve_label(label)

@modcurve_page.route("/interesting")
def interesting():
    return interesting_knowls(
        "modcurve",
        db.gps_gl2zhat_test,
        url_for_modcurve_label,
        title="Some interesting modular curves",
        bread=get_bread("Interesting"),
        learnmore=learnmore_list(),
    )

@modcurve_page.route("/Q/<label>/")
def by_label(label):
    if not LABEL_RE.fullmatch(label):
        flash_error("Invalid label %s", label)
        return redirect(url_for(".index"))
    curve = WebModCurve(label)
    if curve.is_null():
        flash_error("There is no modular curve %s in the database", label)
        return redirect(url_for(".index"))
    return render_template(
        "modcurve.html",
        curve=curve,
        properties=curve.properties,
        friends=curve.friends,
        bread=curve.bread,
        title=curve.title,
        downloads=curve.downloads,
        KNOWL_ID=f"modcurve.{label}",
        learnmore=learnmore_list(),
    )

def url_for_modcurve_label(label):
    return url_for(".by_label", label=label)

def modcurve_lmfdb_label(label):
    if CP_LABEL_RE.fullmatch(label):
        label_type = "Cummins & Pauli label"
        lmfdb_label = db.gps_gl2zhat_test.lucky({"CPlabel": label}, "label")
    elif SZ_LABEL_RE.fullmatch(label):
        label_type = "Sutherland & Zywina label"
        lmfdb_label = db.gps_gl2zhat_test.lucky({"SZlabel": label}, "label")
    elif RZB_LABEL_RE.fullmatch(label):
        label_type = "Rousse & Zureick-Brown label"
        lmfdb_label = db.gps_gl2zhat_test.lucky({"RZBlabel": label}, "label")
    elif S_LABEL_RE.fullmatch(label):
        label_type = "Sutherland label"
        lmfdb_label = db.gps_gl2zhat_test.lucky({"Slabel": label}, "label")
    elif NAME_RE.fullmatch(label.upper()):
        label_type = "name"
        lmfdb_label = db.gps_gl2zhat_test.lucky({"name": canonicalize_name(label)}, "label")
    else:
        label_type = "label"
        lmfdb_label = label
    return lmfdb_label, label_type
    
def modcurve_jump(info):
    labels = (info["jump"]).split("*")
    lmfdb_labels = []    
    for label in labels:
        lmfdb_label, label_type = modcurve_lmfdb_label(label)
        if lmfdb_label is None:
            flash_error("There is no modular curve in the database with %s %s", label_type, label)
            return redirect(url_for(".index"))
        lmfdb_labels.append(lmfdb_label)
    
    if len(lmfdb_labels) == 1:
        label = lmfdb_labels[0]
        return redirect(url_for_modcurve_label(label))
    else:
        factors = list(db.gps_gl2zhat_test.search({"label": {"$in": lmfdb_labels, "$not": "1.1.0.1"}}, "factorization"))
        if len(factors) != len([label for label in lmfdb_labels if label != "1.1.0.1"]):
            flash_error("Fiber product decompositions cannot contain repeated terms")
            return redirect(url_for(".index"))
        factors = sorted(sum(factors, []), key=lambda x:[int(i) for i in x.split(".")])
        label = db.gps_gl2zhat_test.lucky({'factorization': factors}, "label")
        if label is None:
            flash_error("There is no modular curve in the database isomorphic to the fiber product %s", info["jump"])
            return redirect(url_for(".index"))
        else:
            return redirect(url_for_modcurve_label(label))        

modcurve_columns = SearchColumns([
    LinkCol("label", "modcurve.label", "Label", url_for_modcurve_label, default=True),
    ProcessedCol("name", "modcurve.name", "Name", lambda s: name_to_latex(s) if s else "", align="center", default=True),
    MathCol("level", "modcurve.level", "Level", default=True),
    MathCol("index", "modcurve.index", "Index", default=True),
    MathCol("genus", "modcurve.genus", "Genus", default=True),
    ProcessedCol("rank", "modcurve.rank", "Rank", lambda r: "" if r is None else r, default=lambda info: info.get("rank") or info.get("genus_minus_rank"), align="center", mathmode=True),
    ProcessedCol("gonality_bounds", "modcurve.gonality", "$\Q$-gonality", lambda b: r'$%s$'%(b[0]) if b[0] == b[1] else r'$%s \le \gamma \le %s$'%(b[0],b[1]), align="center", default=True),
    MathCol("cusps", "modcurve.cusps", "Cusps", default=True),
    MathCol("rational_cusps", "modcurve.cusps", r"$\Q$-cusps", default=True),
    ProcessedCol("cm_discriminants", "modcurve.cm_discriminants", "CM points", lambda d: r"$\textsf{yes}$" if d else r"$\textsf{no}$", align="center", default=True),
    ProcessedCol("conductor", "ag.conductor", "Conductor", factored_conductor, align="center", mathmode=True),
    CheckCol("simple", "modcurve.simple", "Simple"),
    CheckCol("squarefree", "av.squarefree", "Squarefree"),
    CheckCol("contains_negative_one", "modcurve.contains_negative_one", "Contains -1", short_title="contains -1"),
    ProcessedCol("dims", "modcurve.decomposition", "Decomposition", formatted_dims, align="center"),
])

@search_parser
def parse_family(inp, query, qfield):
    if inp not in ["X0", "X1", "X", "Xsp", "Xspplus", "Xns", "Xnsplus", "XS4", "any"]:
        raise ValueError
    inp = inp.replace("plus", "+")
    if inp == "any":
        query[qfield] = {"$like": "X%"}
    elif inp == "X" or inp == "XS4": #add nothing
        query[qfield] = {"$like": inp + "(%"}
    elif inp == "Xns+" or inp == "Xns": #add X(1)
        query[qfield] = {"$or":[{"$like": inp + "(%"}, {"$in":["X(1)"]}]}
    elif inp == "Xsp": #add X(1),X(2)
        query[qfield] = {"$or":[{"$like": inp + "(%"}, {"$in":["X(1)","X(2)"]}]}
    else: #add X(1),X0(2)
        query[qfield] = {"$or":[{"$like": inp + "(%"}, {"$in":["X(1)","X0(2)"]}]}
        

@search_wrap(
    table=db.gps_gl2zhat_test,
    title="Modular curve search results",
    err_title="Modular curves search input error",
    shortcuts={"jump": modcurve_jump},
    columns=modcurve_columns,
    bread=lambda: get_bread("Search results"),
    url_for_label=url_for_modcurve_label,
)
def modcurve_search(info, query):
    parse_ints(info, query, "level")
    if info.get('level_type'):
        if info['level_type'] == 'prime':
            query['num_bad_primes'] = 1
            query['level_is_squarefree'] = True
        elif info['level_type'] == 'prime_power':
            query['num_bad_primes'] = 1
        elif info['level_type'] == 'squarefree':
            query['level_is_squarefree'] = True
        elif info['level_type'] == 'divides':
            if not isinstance(query.get('level'), int):
                err = "You must specify a single level"
                flash_error(err)
                raise ValueError(err)
            else:
                query['level'] = {'$in': integer_divisors(ZZ(query['level']))}
    parse_family(info, query, "family", qfield="name")
    parse_ints(info, query, "index")
    parse_ints(info, query, "genus")
    parse_ints(info, query, "rank")
    parse_ints(info, query, "genus_minus_rank")
    parse_ints(info, query, "cusps")
    parse_interval(info, query, "gonality", quantifier_type=info.get("gonality_type", "exactly"))
    parse_ints(info, query, "rational_cusps")
    parse_ints(info, query, "nu2")
    parse_ints(info, query, "nu3")
    parse_bool(info, query, "simple")
    parse_bool(info, query, "squarefree")
    parse_bool(info, query, "contains_negative_one")
    if "cm_discriminants" in info:
        if info["cm_discriminants"] == "yes":
            query["cm_discriminants"] = {"$ne": []}
        elif info["cm_discriminants"] == "no":
            query["cm_discriminants"] = []
        elif info["cm_discriminants"] == "-3,-12,-27":
            query["cm_discriminants"] = {"$or": [{"$contains": int(D)} for D in [-3,-12,-27]]}
        elif info["cm_discriminants"] == "-4,-16":
            query["cm_discriminants"] = {"$or": [{"$contains": int(D)} for D in [-4,-16]]}
        elif info["cm_discriminants"] == "-7,-28":
            query["cm_discriminants"] = {"$or": [{"$contains": int(D)} for D in [-7,-28]]}
        else:
            query["cm_discriminants"] = {"$contains": int(info["cm_discriminants"])}
    parse_noop(info, query, "CPlabel")
    parse_element_of(info, query, "covers", qfield="parents", parse_singleton=str)
    parse_element_of(info, query, "factor", qfield="factorization", parse_singleton=str)
    #parse_element_of(info, query, "covered_by", qfield="children")
    if "covered_by" in info:
        # sort of hacky
        parents = db.gps_gl2zhat_test.lookup(info["covered_by"], "parents")
        if parents is None:
            msg = "%s not the label of a modular curve in the database"
            flash_error(msg, info["covered_by"])
            raise ValueError(msg % info["covered_by"])
        query["label"] = {"$in": parents}

class ModCurveSearchArray(SearchArray):
    noun = "curve"
    jump_example = "13.78.3.1"
    jump_egspan = "e.g. 13.78.3.1, XNS+(13), 13Nn, 13A3, or 3.8.0.1*X1(5) (fiber product over $X(1)$)"
    jump_prompt = "Label or name"
    jump_knowl = "modcurve.search_input"

    def __init__(self):
        level_quantifier = SelectBox(
            name="level_type",
            options=[('', ''),
                     ('prime', 'prime'),
                     ('prime_power', 'p-power'),
                     ('squarefree', 'sq-free'),
                     ('divides', 'divides'),
                     ],
            min_width=85)
        level = TextBoxWithSelect(
            name="level",
            knowl="modcurve.level",
            label="Level",
            example="11",
            example_span="2, 11-23",
            select_box=level_quantifier,
        )
        index = TextBox(
            name="index",
            knowl="modcurve.index",
            label="Index",
            example="6",
            example_span="6, 12-100",
        )
        genus = TextBox(
            name="genus",
            knowl="modcurve.genus",
            label="Genus",
            example="1",
            example_span="0, 2-3",
        )
        rank = TextBox(
            name="rank",
            knowl="modcurve.rank",
            label="Rank",
            example="1",
            example_span="0, 2-3",
        )
        genus_minus_rank = TextBox(
            name="genus_minus_rank",
            knowl="modcurve.genus_minus_rank",
            label="Genus-rank difference",
            example="0",
            example_span="0, 1",
        )
        cusps = TextBox(
            name="cusps",
            knowl="modcurve.cusps",
            label="Cusps",
            example="1",
            example_span="1, 4-8",
        )
        rational_cusps = TextBox(
            name="rational_cusps",
            knowl="modcurve.cusps",
            label=r"$\Q$-cusps",
            example="1",
            example_span="0, 4-8",
        )
        gonality_quantifier = SelectBox(
            name="gonality_type",
            options=[('', 'exactly'),
                     ('possibly', 'possibly'),
                     ('atleast', 'at least'),
                     ('atmost', 'at most'),
                     ],
            min_width=85)
        gonality = TextBoxWithSelect(
            name="gonality",
            knowl="modcurve.gonality",
            label="$\Q$-gonality",
            example="2",
            example_span="2, 3-6",
            select_box=gonality_quantifier,
        )
        nu2 = TextBox(
            name="nu2",
            knowl="modcurve.elliptic_points",
            label="Elliptic points of order 2",
            example="1",
            example_span="1,3-5",
        )
        nu3 = TextBox(
            name="nu3",
            knowl="modcurve.elliptic_points",
            label="Elliptic points of order 3",
            example="1",
            example_span="1,3-5",
        )        
        factor = TextBox(
            name="factor",
            knowl="modcurve.fiber_product",
            label="Fiber product with",
            example="3.8.0.1",
        )
        covers = TextBox(
            name="covers",
            knowl="modcurve.modular_cover",
            label="Minimally covers",
            example="1.1.0.1",
        )
        covered_by = TextBox(
            name="covered_by",
            knowl="modcurve.modular_cover",
            label="Minimally covered by",
            example="6.12.0.1",
        )
        simple = YesNoBox(
            name="simple",
            knowl="modcurve.simple",
            label="Simple",
            example_col=True,
        )
        squarefree = YesNoBox(
            name="squarefree",
            knowl="av.squarefree",
            label="Squarefree",
            example_col=True,
        )
        cm_opts = ([('', ''), ('yes', 'rational CM points'), ('no', 'no rational CM points')] +
                   [('-4,-16', 'CM field Q(sqrt(-1))'), ('-3,-12,-27', 'CM field Q(sqrt(-3))'), ('-7,-28', 'CM field Q(sqrt(-7))')] +
                   [('-%d'%d, 'CM discriminant -%d'%d) for  d in [3,4,7,8,11,12,16,19,27,38,43,67,163]])
        cm_discriminants = SelectBox(
            name="cm_discriminants",
            options=cm_opts,
            knowl="modcurve.cm_discriminants",
            label="CM points",
            example="yes, no, CM discriminant -3"
        )
        contains_negative_one = YesNoBox(
            name="contains_negative_one",
            knowl="modcurve.contains_negative_one",
            label="Contains $-I$",
            example_col=True,
        )
        family = SelectBox(
            name="family",
            options=[("", ""),
                     ("X0", "X0(N)"),
                     ("X1", "X1(N)"),
                     ("X", "X(N)"),
                     ("Xsp", "Xsp(N)"),
                     ("Xns", "Xns(N)"),
                     ("Xspplus", "Xsp+(N)"),
                     ("Xnsplus", "Xns+(N)"),
                     ("XS4", "XS4(N)"),
                     ("any", "any")],
            knowl="modcurve.standard",
            label="Family",
            example="X0(N), Xsp(N)")
        CPlabel = SneakyTextBox(
            name="CPlabel",
            knowl="modcurve.other_labels",
            label="CP label",
            example="3B0",
        )
        count = CountBox()

        self.browse_array = [
            [level, index],
            [genus, rank],
            [genus_minus_rank, gonality],
            [cusps, rational_cusps],
            [nu2, nu3],
            [simple, squarefree],
            [cm_discriminants, factor],
            [covers, covered_by],
            [contains_negative_one, family],
            [count],
        ]

        self.refine_array = [
            [level, index, genus, rank, genus_minus_rank],
            [gonality, cusps, rational_cusps, nu2, nu3],
            [simple, squarefree, cm_discriminants, factor, covers],
            [covered_by, contains_negative_one, family, CPlabel],
        ]

    sort_knowl = "modcurve.sort_order"
    sorts = [
        ("", "level", ["level", "index", "genus", "label"]),
        ("index", "index", ["index", "level", "genus", "label"]),
        ("genus", "genus", ["genus", "level", "index", "label"]),
        ("rank", "rank", ["rank", "genus", "level", "index", "label"]),
    ]
    null_column_explanations = {
        'simple': False,
        'squarefree': False,
        'rank': False,
        'genus_minus_rank': False,
    }

@modcurve_page.route("/Q/low_degree_points")
def low_degree_points():
    info = to_dict(request.args, search_array=RatPointSearchArray())
    return rational_point_search(info)

ratpoint_columns = SearchColumns([
    LinkCol("curve_label", "modcurve.label", "Label", url_for_modcurve_label, default=True),
    ProcessedCol("curve_name", "modcurve.family", "Name", name_to_latex, default=True),
    MathCol("curve_genus", "modcurve.genus", "Genus", default=True),
    MathCol("degree", "modcurve.point_degree", "Degree", default=True),
    ProcessedCol("isolated", "modcurve.isolated_point", "Isolated",
                 lambda x: r"$\textsf{yes}$" if x == 1 else (r"$\textsf{no}$" if x == -1 else r"$\textsf{maybe}$"),
                 default=True),
    ProcessedCol("cm_discriminant", "ec.complex_multiplication", "CM", lambda v: "" if v == 0 else v,
                 short_title="CM discriminant", mathmode=True, align="center", default=True, orig="cm"),
    LinkCol("Elabel", "modcurve.elliptic_curve_of_point", "Elliptic curve", lambda Elabel: url_for_ECNF_label(Elabel) if "-" in Elabel else url_for_EC_label(Elabel), default=True),
    ProcessedCol("residue_field", "modcurve.point_residue_field", "Residue field", lambda field: nf_display_knowl(field, field_pretty(field)), default=True, align="center"),
    ProcessedCol("j_field", "ec.j_invariant", r"$\Q(j)$", lambda field: nf_display_knowl(field, field_pretty(field)), default=True, align="center", short_title="Q(j)"),
    MultiProcessedCol("jinv", "ec.j_invariant", "$j$-invariant", ["jinv", "j_field", "jorig", "residue_field"], showj_nf, default=True),
    FloatCol("j_height", "ec.j_height", "$j$-height", default=True)])

@search_wrap(
    table=db.modcurve_points,
    title="Modular curve low-degree point search results",
    err_title="Modular curves low-degree point search input error",
    columns=ratpoint_columns,
    bread=lambda: get_bread("Low-degree point search results"),
)
def rational_point_search(info, query):
    parse_noop(info, query, "curve", qfield="curve_label")
    parse_ints(info, query, "genus", qfield="curve_genus")
    parse_ints(info, query, "level", qfield="curve_level")
    parse_family(info, query, "family", qfield="curve_name")
    parse_ints(info, query, "degree")
    parse_nf_string(info, query, "residue_field")
    parse_nf_string(info, query, "j_field")
    j_field = query.get("j_field")
    if not j_field:
        j_field = query.get("residue_field")
    parse_nf_jinv(info, query, "jinv", field_label=j_field)
    parse_floats(info, query, "j_height")
    if 'cm' in info:
        if info['cm'] == 'noCM':
            query['cm'] = 0
        elif info['cm'] == 'CM':
            query['cm'] = {'$ne': 0}
        else:
            parse_ints(info, query, 'cm')
    parse_bool_unknown(info, query, "isolated")

class RatPointSearchArray(SearchArray):
    noun = "point"
    sorts = [("", "level", ["curve_level", "curve_genus", "curve_index", "curve_label", "degree", "conductor_norm", "j_height", "jinv"]),
             ("curve_genus", "genus", ["curve_genus", "curve_level", "curve_index", "curve_label", "degree", "conductor_norm", "j_height", "jinv"]),
             ("degree", "degree", ["degree", "curve_level", "curve_genus", "curve_index", "curve_label", "conductor_norm", "j_height", "jinv"]),
             ("j_height", "height of j-invariant", ["j_height", "jinv", "conductor_norm", "degree", "curve_level", "curve_genus", "curve_index", "curve_label"]),
             ("conductor", "minimal conductor norm", ["conductor_norm", "j_height", "jinv", "degree", "curve_level", "curve_genus", "curve_index", "curve_label"]),
             ("residue_field", "residue field", ["degree", "residue_field", "curve_level", "curve_genus", "curve_index", "curve_label", "conductor_norm", "j_height", "jinv"]),
             ("cm", "CM discriminant", ["cm", "degree", "curve_level", "curve_genus", "curve_index", "curve_label", "conductor_norm", "j_height", "jinv"])]
    def __init__(self):
        curve = TextBox(
            name="curve",
            knowl="modcurve.label",
            label="Curve",
            example="11.12.1.1",
        )
        genus = TextBox(
            name="genus",
            knowl="modcurve.genus",
            label="Genus",
            example="1-3",
        )
        level = TextBox(
            name="level",
            knowl="modcurve.level",
            label="Level",
            example="37"
        )
        degree = TextBox(
            name="degree",
            knowl="modcurve.degree",
            label="Degree",
            example="2-4",
        )
        residue_field = TextBox(
            name="residue_field",
            knowl="modcurve.point_residue_field",
            label="Residue field",
            example="2.0.4.1",
        )
        j_field = TextBox(
            name="j_field",
            knowl="ec.j_invariant",
            label=r"$\Q(j)$",
            example="2.0.4.1",
        )
        jinv = TextBox(
            name="jinv",
            knowl="ec.j_invariant",
            label="$j$-invariant",
            example="30887/73-9927/73*a",
        )
        j_height = TextBox(
            name="j_height",
            knowl="ec.j_height",
            label="$j$-height",
            example="1.0-4.0",
        )
        cm_opts = ([('', ''), ('noCM', 'no potential CM'), ('CM', 'potential CM')] +
                   [('-4,-16', 'CM field Q(sqrt(-1))'), ('-3,-12,-27', 'CM field Q(sqrt(-3))'), ('-7,-28', 'CM field Q(sqrt(-7))')] +
                   [('-%d'%d, 'CM discriminant -%d'%d) for  d in [3,4,7,8,11,12,16,19,27,38,43,67,163]])
        cm = SelectBox(
            name="cm",
            label="Complex multiplication",
            example="potential CM by Q(i)",
            knowl="ec.complex_multiplication",
            options=cm_opts,
        )
        isolated = YesNoMaybeBox(
            "isolated",
            label="Isolated",
            knowl="modcurve.isolated_point",
        )
        family = SelectBox(
            name="family",
            options=[("", ""),
                     ("X0", "X0(N)"),
                     ("X1", "X1(N)"),
                     ("X", "X(N)"),
                     ("Xsp", "Xsp(N)"),
                     ("Xns", "Xns(N)"),
                     ("Xspplus", "Xsp+(N)"),
                     ("Xnsplus", "Xns+(N)"),
                     ("XS4", "XS4(N)"),
                     ("any", "any")],
            knowl="modcurve.standard",
            label="Family",
            example="X0(N), Xsp(N)")

        self.refine_array = [[curve, level, genus, degree, cm],
                             [residue_field, j_field, jinv, j_height, isolated],
                             [family]]

class ModCurve_stats(StatsDisplay):
    def __init__(self):
        self.ncurves = comma(db.gps_gl2zhat_test.count())
        self.max_level = db.gps_gl2zhat_test.max("level")

    @property
    def short_summary(self):
        modcurve_knowl = display_knowl("modcurve", title="modular curves")
        return (
            fr'The database currently contains {self.ncurves} {modcurve_knowl} of level $N\le {self.max_level}$ parameterizing elliptic curves $E$ over $\Q$.  You can <a href="{url_for(".statistics")}">browse further statistics</a>.'
        )

    @property
    def summary(self):
        modcurve_knowl = display_knowl("modcurve", title="modular curves")
        return (
            fr'The database currently contains {self.ncurves} {modcurve_knowl} of level $N\le {self.max_level}$ parameterizing elliptic curves $E/\Q$.'
        )

    table = db.gps_gl2zhat_test
    baseurl_func = ".index"
    buckets = {'level': ['1-4', '5-8', '9-12', '13-16', '17-20', '21-'],
               'genus': ['0', '1', '2', '3', '4-6', '7-20', '21-100', '101-'],
               'rank': ['0', '1', '2', '3', '4-6', '7-20', '21-100', '101-'],
               'gonality': ['1', '2', '3', '4', '5-8', '9-'],
               }
    knowls = {'level': 'modcurve.level',
              'genus': 'modcurve.genus',
              'rank': 'modcurve.rank',
              'gonality': 'modcurve.gonality',
              }
    stat_list = [
        {'cols': ['level', 'genus'],
         'proportioner': proportioners.per_row_total,
         'totaler': totaler()},
        {'cols': ['genus', 'rank'],
         'proportioner': proportioners.per_row_total,
         'totaler': totaler()},
        {'cols': ['genus', 'gonality'],
         'proportioner': proportioners.per_row_total,
         'totaler': totaler()},
    ]

@modcurve_page.route("/Q/stats")
def statistics():
    title = 'Modular curves: Statistics'
    return render_template("display_stats.html", info=ModCurve_stats(), title=title, bread=get_bread('Statistics'), learnmore=learnmore_list())

@modcurve_page.route("/Source")
def how_computed_page():
    t = r'Source and acknowledgments for modular curve data'
    bread = get_bread('Source')
    return render_template("multi.html",
                           kids=['rcs.source.modcurve',
                           'rcs.ack.modcurve',
                           'rcs.cite.modcurve'],
                           title=t, bread=bread, learnmore=learnmore_list_remove('Source'))

@modcurve_page.route("/Completeness")
def completeness_page():
    t = r'Completeness of modular curve data'
    bread = get_bread('Completeness')
    return render_template("single.html", kid='rcs.cande.modcurve',
                           title=t, bread=bread, learnmore=learnmore_list_remove('Completeness'))

@modcurve_page.route("/Reliability")
def reliability_page():
    t = r'Reliability of modular curve data'
    bread = get_bread('Reliability')
    return render_template("single.html", kid='rcs.rigor.modcurve',
                           title=t, bread=bread, learnmore=learnmore_list_remove('Reliability'))

@modcurve_page.route("/Labels")
def labels_page():
    t = r'Labels for modular curves'
    bread = get_bread('Labels')
    return render_template("single.html", kid='modcurve.label',
                           title=t, bread=bread, learnmore=learnmore_list_remove('labels'))

@modcurve_page.route("/data/<label>")
def modcurve_data(label):
    bread = get_bread([(label, url_for_modcurve_label(label)), ("Data", " ")])
    if LABEL_RE.fullmatch(label):
        return datapage([label], ["gps_gl2zhat_test"], title=f"Modular curve data - {label}", bread=bread)
    else:
        return abort(404)

class ModCurve_download(Downloader):
    table = db.gps_gl2zhat_test
    title = "Modular curves"
    #columns = ['level', 'genus', 'plane_model']
    #data_format = []
    #data_description = []

    function_body = {
        "magma": [
            #"return data[3];"
        ],
        "sage": [
            #"return data[3]"
        ],
    }

# cols currently unused in individual page download
    #'cusp_orbits',
    #'determinant_label',
    #'dims',
    #'gassmann_class',
    #'genus_minus_rank',
    #'isogeny_orbits',
    #'kummer_orbits',
    #'level_is_squarefree',
    #'level_radical',
    #'log_conductor',
    #'newforms',
    #'nu2',
    #'nu3',
    #'num_bad_primes',
    #'obstructions',
    #'orbits',
    #'pointless',
    #'psl2index',
    #'psl2level',
    #'qtwists',
    #'rational_cusps',
    #'reductions',
    #'scalar_label',
    #'simple',
    #'sl2level',
    #'squarefree',
    #'tiebreaker',
    #'trace_hash',
    #'traces',
# cols currently unused in modcurve_models
    #'dont_display'
    #'gonality_bounds'
    #'modcurve'
# cols currently unused in modcurve_modelmaps
    #'domain_label',
    #'dont_display',
    #'factored'
    
    def download_modular_curve_magma_str(self, label):
        s = ""
        rec = db.gps_gl2zhat_test.lookup(label)
        if rec is None:
            return abort(404, "Label not found: %s" % label)
        s += "// Magma code for modular curve with label %s\n\n" % label
        if rec['name'] or rec['CPlabel'] or rec['Slabel'] or rec['SZlabel'] or rec['RZBlabel']:
            s += "// Other names and/or labels\n"
            if rec['name']:
                s += "// Curve name: %s\n" % rec['name']
            if rec['CPlabel']:
                s += "// Cummins-Pauli label: %s\n" % rec['CPlabel']
            if rec['RZBlabel']:
                s += "// Rouse-Zureick-Brown label: %s\n" % rec['RZBlabel']
            if rec['Slabel']:
                s += "// Sutherland label: %s\n" % rec['Slabel']
            if rec['SZlabel']:
                s += "// Sutherland-Zywina label: %s\n" % rec['SZlabel']
        s += "\n// Group data\n"
        s += "level := %s;\n" % rec['level']
        s += "// Elements that, together with Gamma(level), generate the group\n"
        s += "gens := %s;\n" % rec['generators']
        s += "// Group contains -1?\n"
        if rec['contains_negative_one']:
            s += "ContainsMinus1 := true;\n"
        else:
            s += "ContainsMinus1 := false;\n"
        s += "// Index in Gamma(1)\n"
        s += "index := %s;\n" % rec['index']
        s += "\n// Curve data\n"
        s += "conductor := %s;\n" % rec['conductor']
        s += "bad_primes := %s;\n" % rec['bad_primes']
        s += "// Genus\n"
        s += "g := %s;\n" % rec['genus']
        s += "// Rank\n"
        s += "r := %s\n;" % rec['rank']
        if rec['gonality'] != -1:
            s += "// Exact gonality known\n"
            s += "gamma := %s;\n" % rec['gonality']
        else:
            s += "// Exact gonality unknown, but contained in following interval\n"
            s += "gamma_int := %s;\n" % rec['gonality_bounds']
        s += "\n// Modular data\n"
        s += "// Number of cusps\n"
        s += "Ncusps := %s\n;" % rec['cusps']
        s += "// Number of rational cusps\n"
        s += "Nrat_cusps := %s\n;" % rec['cusps']
        s += "// CM discriminants\n"
        s += "CM_discs := %s;\n" % rec['cm_discriminants']
        if rec['factorization'] != [label]:
            s += "// Modular curve is a fiber product of the following curves"
            s += "factors := %s\n" % [f.replace("'", "\"") for f in rec['factorization']]
        s += "// Groups containing given group, corresponding to curves covered by given curve\n"
        parents_mag = "%s" % rec['parents']
        parents_mag = parents_mag.replace("'", "\"")
        s += "covers := %s;\n" % parents_mag

        
        s += "\n// Models for this modular curve, if computed\n"
        models = list(db.modcurve_models.search(
            {"modcurve": label, "model_type":{"$not":1}},
            ["equation", "number_variables", "model_type", "smooth"]))
        if models:
            max_nb_variables = max([m["number_variables"] for m in models])
            variables = ascii_lowercase[-max_nb_variables:]
            s += "K<%s" % variables[0]
            for x in variables[1:]:
                s += ",%s" % x
            s += "> := PolynomialRing(Rationals(), %s);\n" % max_nb_variables
        
        s += "// Isomorphic to P^1?\n"
        is_P1 = "true" if (rec['genus'] == 0 and rec['pointless'] is False) else "false"
        s += "is_P1 := %s\n" % is_P1
        model_id = 0
        for m in models:
            if m["model_type"] == 0:
                name = "Canonical model"
            elif m["model_type"] == 2:
                if m["smooth"] is True:
                    name = "Smooth plane model"
                elif m["smooth"] is False:
                    name = "Singular plane model"
                else:
                    name = "Plane model"
            else:
                name = "Other model"
            s += "\n// %s\n" % name
            s += "model_%s := " % model_id
            s += "%s" % m['equation']
            s += "\n"
            model_id += 1

        s += "\n// Maps from this modular curve, if computed\n"
        maps = list(db.modcurve_modelmaps.search(
            {"domain_label": label},
            ["domain_model_type", "codomain_label", "codomain_model_type",
             "coordinates", "leading_coefficients"]))
        codomain_labels = [m["codomain_label"] for m in maps]
        codomain_models = list(db.modcurve_models.search(
            {"modcurve": {"$in": codomain_labels}},
            ["equation", "modcurve", "model_type"]))
        map_id = 0
        if maps and is_P1: #variable t has not been introduced above
            s += "K<t> := PolynomialRing(Rationals());\n"
        
        for m in maps:
            prefix = "map_%s_" % map_id
            has_codomain_equation = False
            if m["codomain_label"] == "1.1.0.1":
                if m["codomain_model_type"] == 1:
                    name = "j-invariant map"
                elif m["codomain_model_type"] == 3:
                    name = "j-invariant minus 1728"
                elif m["codomain_model_type"] == 4:
                    name = "E4, E6"
                else:
                    name = "Other map to X(1)"
            else:
                name = "Map"
            if m["domain_model_type"] == 0:
                name += " from the canonical model"
            elif m["domain_model_type"] == 2:
                name += " from the plane model"
            if m["codomain_label"] != "1.1.0.1":
                has_codomain_equation = True
                if m["codomain_label_type"] == 0:
                    name += " to canonical model of modular curve"
                elif m["codomain_label_type"] == 1:
                    has_codomain_equation = False
                    name += " to modular curve isomorphic to P^1"
                elif m["codomain_label_type"] == 2:
                    name += " to plane model of modular curve"
                else:
                    name += " to other model of modular curve"
                name += " with label %s" % m["codomain_label"]
            s += "\n// %s\n" % name
            nb_affines = len(m["coordinates"])
            if nb_affines > 1:
                s += "// Equations are available on %s different open affines\n" % nb_affine
            for i in range(nb_affines):
                if nb_affines > 1:
                    s += "\n// On open affine no. %s:\n" % i
                suffix = "open_%s" % i if nb_affines > 1 else ""
                coord = m["coordinates"][i]
                if m["leading_coefficients"] is None:
                    lead = [1]*len(coord)
                else:
                    lead = m["leading_coefficients"][i]
                for j in range(len(coord)):
                    s += "//   Coordinate number %s:\n" % j
                    s += prefix + suffix + ("coord_%s := " % j)
                    s += "%s*(" % lead[j]
                    s += "%s)\n" % coord[j]
            if has_codomain_equation:
                s += "// Codomain equation:\n"
                eq = [eq for eq in codomain_models if eq["modcurve"] == m["codomain_label"] and eq["model_type"] == m["codomain_model_type"]][0]
                s += prefix + "codomain := " + "%s\n" % eq["equation"]            
            map_id += 1
        return s

    def download_modular_curve_magma(self, label):
        s = self.download_modular_curve_magma_str(label)
        return self._wrap(s, label, lang="magma")

    def download_modular_curve_sage(self, label):
        s = self.download_modular_curve_magma_str(label)
        s = s.replace(":=", "=")
        s = s.replace(";", "")
        s = s.replace("//", "#")
        s = s.replace("K<", "K.<")
        return self._wrap(s, label, lang="sage")

    def download_modular_curve(self, label, lang):
        if lang == "magma":
            return self.download_modular_curve_magma(label)
        elif lang == "sage":
            return self.download_modular_curve_sage(label)
        elif lang == "text":
            data = db.gps_gl2zhat_test.lookup(label)
            if data is None:
                return abort(404, "Label not found: %s" % label)
            return self._wrap(Json.dumps(data),
                              label,
                              title='Data for modular curve with label %s,'%label)

@modcurve_page.route("/download_to_magma/<label>")
def modcurve_magma_download(label):
    return ModCurve_download().download_modular_curve(label, lang="magma")

@modcurve_page.route("/download_to_sage/<label>")
def modcurve_sage_download(label):
    return ModCurve_download().download_modular_curve(label, lang="sage")

@modcurve_page.route("/download_to_text/<label>")
def modcurve_text_download(label):
    return ModCurve_download().download_modular_curve(label, lang="text")

