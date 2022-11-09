# -*- coding: utf-8 -*-

from collections import Counter
from flask import url_for

from sage.all import lazy_attribute, prod, euler_phi, ZZ, QQ, latex, PolynomialRing, lcm, NumberField, FractionField
from lmfdb.utils import WebObj, integer_prime_divisors, teXify_pol, web_latex, pluralize
from lmfdb import db
from lmfdb.classical_modular_forms.main import url_for_label as url_for_mf_label
from lmfdb.elliptic_curves.web_ec import latex_equation as EC_equation
from lmfdb.elliptic_curves.elliptic_curve import url_for_label as url_for_EC_label
from lmfdb.ecnf.main import url_for_label as url_for_ECNF_label
from lmfdb.number_fields.number_field import url_for_label as url_for_NF_label
from string import ascii_lowercase

def get_bread(tail=[]):
    base = [("Modular curves", url_for(".index")), (r"$\Q$", url_for(".index_Q"))]
    if not isinstance(tail, list):
        tail = [(tail, " ")]
    return base + tail

def showexp(c, wrap=True):
    if c == 1:
        return ""
    elif wrap:
        return f"$^{{{c}}}$"
    else:
        return f"^{{{c}}}"

def showj(j):
    if j[0] == 0:
        return "$0$"
    elif j[1] == 1:
        return f"${j[0]}$"
    else:
        return r"$\tfrac{%s}{%s}$" % tuple(j)

def showj_fac(j):
    if j[0] == 0 or j[1] == 1 and ZZ(j[0]).is_prime():
        return ""
    else:
        return "$= %s$" % latex((ZZ(j[0]) / ZZ(j[1])).factor())

def showj_nf(j, jfield, jorig, resfield):
    Ra = PolynomialRing(QQ, 'a')
    if "," in j:
        s = None
        f = Ra([QQ(c) for c in j.split(",")])
        if jfield.startswith("2."):
            D = ZZ(jfield.split(".")[2])
            if jfield.split(".")[1] == "0":
                D = -D
            x = Ra.gen()
            if D % 4 == 1:
                K = NumberField(x**2 - x - (D - 1)//4, 'a')
            else:
                K = NumberField(x**2 - D//4, 'a')
            if K.class_number() == 1:
                jj = K((f).padded_list(K.degree()))
                jfac = latex(jj.factor())
                s = f"${jfac}$"
        if s is None:
            d = f.denominator()
            if d == 1:
                s = web_latex(f)
            else:
                s = fr"$\tfrac{{1}}{{{latex(d.factor())}}} \left({latex(d*f)}\right)$"
    else:
        if "/" in j:
            fac = f" = {latex(QQ(j).factor())}"
            a, b = j.split("/")
            s = r"$\tfrac{%s}{%s}%s$" % (a, b, fac)
        elif j != "0":
            s = f"${j} = {latex(ZZ(j).factor())}$"
        else:
            s = "$0$"
    if resfield == "1.1.1.1":
        url = url_for("ec.rational_elliptic_curves", jinv=j, showcol="jinv")
    else:
        if jorig is None:
            jorig = j
        # ECNF search wants j-invariants formatted as a polynomial
        if "," in j:
            j = str(f).replace(" ", "")
        url = url_for("ecnf.index", jinv=j, field=resfield, showcol="jinv")
    return '<a href="%s">%s</a>' % (url, s)

def canonicalize_name(name):
    cname = "X" + name[1:].lower().replace("_", "").replace("^", "")
    if cname[:4] == "Xs4(":
        cname = cname.upper()
    return cname

def canonicalize_family_name(name):
    n = len(name)
    cname = "X" + name[1:].lower().replace("_", "").replace("^", "")
    cname = cname.split("(")[0]
    cname = cname + "(N)"
    if cname[:4] == "Xs4(":
        cname = cname.upper()
    return cname

def name_to_latex(name):
    if not name:
        return ""
    name = canonicalize_name(name)
    if "+" in name:
        name = name.replace("+", "^+")
    if "ns" in name:
        name = name.replace("ns", "{\mathrm{ns}}")
    elif "sp" in name:
        name = name.replace("sp", "{\mathrm{sp}}")
    elif "S4" in name:
        name = name.replace("S4", "{S_4}")
    if name[1] != "(":
        name = "X_" + name[1:]
    return f"${name}$"

def name_to_family_latex(name):
    if not name:
        return ""
    name = canonicalize_family_name(name)
    if "+" in name:
        name = name.replace("+", "^+")
    if "ns" in name:
        name = name.replace("ns", "{\mathrm{ns}}")
    elif "sp" in name:
        name = name.replace("sp", "{\mathrm{sp}}")
    elif "S4" in name:
        name = name.replace("S4", "{S_4}")
    if name[1] != "(":
        name = "X_" + name[1:]
    return f"${name}$"



def factored_conductor(conductor):
    return "\\cdot".join(f"{p}{showexp(e, wrap=False)}" for (p, e) in conductor) if conductor else "1"

def remove_leading_coeff(jfac):
    if "(%s)" % jfac.unit() == (str(jfac).split("*")[0]).replace(' ',''):
        return "*".join(str(jfac).split("*")[1:])
    else:
        return str(jfac)

def formatted_dims(dims):
    if not dims:
        return ""
    C = Counter(dims)
    return "$" + "\cdot".join(f"{d}{showexp(c, wrap=False)}" for (d, c) in sorted(C.items())) + "$"

def formatted_newforms(newforms):
    if not newforms:
        return ""
    C = Counter(newforms)
    # Make sure that the Counter doesn't break the ordering
    return ", ".join(f'<a href="{url_for_mf_label(label)}">{label}</a>{showexp(c)}' for (label, c) in C.items())

def formatted_model(m):
    lines = [teXify_pol(l).lower() for l in m["equation"].replace(" ","").split("=")]
    if len(lines)>2: #display as 0 = ...
        lines = ["0"] + [l for l in lines if l != "0"]
    return (lines, list(range(len(lines)-2)), m["number_variables"], m["model_type"],  m["smooth"])

def formatted_map(m, codomain_name="X(1)", codomain_equation=""):
    f = {}
    for key in ["degree", "domain_model_type", "codomain_label", "codomain_model_type"]:
        f[key] = m[key]
    f["codomain_name"] = codomain_name
    f["codomain_equation"] = codomain_equation
    nb_coords = len(m["coordinates"][0])
    lead = m["leading_coefficients"]
    if lead is None:
        lead = ["1"]*nb_coords
    else:
        lead = lead[0]
    eqs = [teXify_pol(p) for p in m["coordinates"][0]]
    if nb_coords == 2 and not (f["codomain_label"] == "1.1.0.1" and f["codomain_model_type"] == 4):
        nb_coords = 1
        f["coord_names"] = ["f"]
    elif nb_coords <= 12: #p',...,z'
        f["coord_names"] = [x+"'" for x in ascii_lowercase[-nb_coords]]
    else: #x0,...,xn
        f["coord_names"] = ["x_{}".format(i) for i in [0..nb_coords-1]]
    f["nb_coords"] = nb_coords

    if nb_coords == 1: #display only one coordinate as a quotient
        if eqs[1] == "1" and lead == ["1","1"]:
            equations = [eqs[0]]
        elif eqs[1] == "1" and lead[1] == "1" and m["factored"] and eqs[0].count("(") > 0:
            equations = ["{}{}".format(lead[0], eqs[0])]
        elif eqs[1] == "1" and lead[1] == "1":
            equations = ["{}({})".format(lead[0], eqs[0])]
        elif eqs[1] == "1":
            equations = [r"\frac{%s}{%s}" % (eqs[0], lead[0])]
        elif lead == ["1","1"]:
            equations = [r"\frac{%s}{%s}" % (eqs[0], eqs[1])]
        elif lead[1] == "1":
            equations = [r"%s\,\frac{%s}{%s}" % (lead[0], eqs[0], eqs[1])]
        else:
            equations = [r"\frac{%s}{%s}\cdot\frac{%s}{%s}" % (lead[0], lead[1], eqs[0], eqs[1])]
    else: #2 or more coordinates, do not display as quotients
        equations = []
        for j in range(len(eqs)):
            if lead[j] == "1":
                equations.append(eqs[j])
            elif m["factored"] and eqs[j].count("(") > 0:
                equations.append("{}{}".format(lead[j], eqs[j]))
            else:
                equations.append("{}({})".format(lead[j], eqs[j]))
    f["equations"] = equations
    return(f)

def difference(A,B):
    C = A.copy()
    for f in B:
        if f in C:
            C.pop(C.index(f))
    return C

def modcurve_link(label):
    return '<a href="%s">%s</a>'%(url_for(".by_label",label=label),label)

class WebModCurve(WebObj):
    table = db.gps_gl2zhat_test

    @lazy_attribute
    def properties(self):
        props = [
            ("Label", self.label),
            ("Level", str(self.level)),
            ("Index", str(self.index)),
            ("Genus", str(self.genus)),
        ]
        if hasattr(self,"rank"):
            props.append(("Analytic rank", str(self.rank)))
        props.extend([("Cusps", str(self.cusps)),
                      (r"$\Q$-cusps", str(self.rational_cusps))])
        return props

    @lazy_attribute
    def friends(self):
        friends = []
        if self.simple:
            friends.append(("Modular form " + self.newforms[0], url_for_mf_label(self.newforms[0])))
            if self.genus == 1:
                s = self.newforms[0].split(".")
                label = s[0] + "." + s[2]
                friends.append(("Isogeny class " + label, url_for("ec.by_ec_label", label=label)))
            if self.genus == 2:
                g2c_url = db.lfunc_instances.lucky({'Lhash':str(self.trace_hash), 'type' : 'G2Q'}, 'url')
                if g2c_url:
                    s = g2c_url.split("/")
                    label = s[2] + "." + s[3]
                    friends.append(("Isogeny class " + label, url_for("g2c.by_label", label=label)))
            friends.append(("L-function", "/L" + url_for_mf_label(self.newforms[0])))
        else:
            friends.append(("L-function not available",""))
        if self.genus > 0:
            for r in self.table.search({'trace_hash':self.trace_hash},['label','name','newforms']):
                if r['newforms'] == self.newforms and r['label'] != self.label:
                    friends.append(("Modular curve " + (r['name'] if r['name'] else r['label']),url_for("modcurve.by_label", label=r['label'])))
        return friends

    @lazy_attribute
    def bread(self):
        tail = []
        A = ["level", "index", "genus"]
        D = {}
        for a in A:
            D[a] = getattr(self, a)
            tail.append(
                (str(D[a]), url_for(".index_Q", **D))
            )
        tail.append((self.label, " "))
        return get_bread(tail)

    @lazy_attribute
    def title(self):
        if self.name:
            return f"Modular curve {name_to_latex(self.name)}"
        else:
            return f"Modular curve {self.label}"
        
    @lazy_attribute
    def latex_name(self):
        return name_to_latex(self.name)
    
    @lazy_attribute
    def latex_family_name(self):
        return name_to_family_latex(self.name)
        

    @lazy_attribute
    def formatted_dims(self):
        return formatted_dims(self.dims)

    @lazy_attribute
    def formatted_newforms(self):
        return formatted_newforms(self.newforms)

    @lazy_attribute
    def obstruction_primes(self):
        if len(self.obstructions) < 10:
            return ",".join(str(p) for p in self.obstructions if p != 0)
        else:
            return ",".join(str(p) for p in self.obstructions[:3] if p != 0) + r",\ldots," + str(self.obstructions[-1])

    @lazy_attribute
    def qtwist_description(self):
        if self.contains_negative_one:
            if len(self.qtwists) > 1:
                return r"yes"
            else:
                return r"yes"
        else:
            return r"no $\quad$ (see %s for the level structure with $-I$)"%(modcurve_link(self.qtwists[0]))

    @lazy_attribute
    def quadratic_refinements(self):
        if self.contains_negative_one:
            if len(self.qtwists) > 1:
                return r"%s"%(', '.join([modcurve_link(label) for label in self.qtwists[1:]]))
            else:
                return r"none"
        else:
            return "none"

    @lazy_attribute
    def cusp_display(self):
        if self.cusps == 1:
            return "$1$ (which is rational)"
        elif self.rational_cusps == 0:
            return f"${self.cusps}$ (none of which are rational)"
        elif self.rational_cusps == 1:
            return f"${self.cusps}$ (of which $1$ is rational)"
        elif self.cusps == self.rational_cusps:
            return f"${self.cusps}$ (all of which are rational)"
        else:
            return f"${self.cusps}$ (of which ${self.rational_cusps}$ are rational)"

    @lazy_attribute
    def cm_discriminant_list(self):
        return ",".join(str(D) for D in self.cm_discriminants)

    @lazy_attribute
    def factored_conductor(self):
        return factored_conductor(self.conductor)

    @lazy_attribute
    def models_to_display(self):
        return list(db.modcurve_models.search({"modcurve": self.label, "dont_display": False}, ["equation", "number_variables", "model_type", "smooth"]))

    @lazy_attribute
    def formatted_models(self):
        return [formatted_model(m) for m in self.models_to_display]

    @lazy_attribute
    def models_count(self):
        return db.modcurve_models.count({"modcurve": self.label})

    @lazy_attribute
    def has_more_models(self):
        return len(self.models_to_display) < self.models_count
    
    @lazy_attribute
    def modelmaps_to_display(self):
        # Ensure domain model and map have dont_display = False
        domain_types = [1] + [m["model_type"] for m in self.models_to_display]
        return list(db.modcurve_modelmaps.search(
            {"domain_label": self.label,
             "dont_display": False,
             "domain_model_type":{"$in": domain_types}},
            ["degree", "domain_model_type", "codomain_label", "codomain_model_type",
             "coordinates", "leading_coefficients", "factored"]))

    def display_j(self, domain_model_type):
        jmaps = [m for m in self.modelmaps_to_display if m["codomain_label"] == "1.1.0.1" and m["domain_model_type"] == domain_model_type]
        return len(jmaps) >= 1

    def display_E4E6(self, domain_model_type):
        jmaps = [m for m in self.modelmaps_to_display if m["codomain_label"] == "1.1.0.1" and m["codomain_model_type"] == 4 and m["domain_model_type"] == domain_model_type]
        return len(jmaps) >= 1

    def formatted_jmap(self, domain_model_type):
        jmaps = [m for m in self.modelmaps_to_display if m["codomain_label"] == "1.1.0.1" and m["domain_model_type"] == domain_model_type]
        jmap = [m for m in jmaps if m["codomain_model_type"] == 1]
        j1728map = [m for m in jmaps if m["codomain_model_type"] == 3]
        f1 = formatted_map(jmap[0]) if jmap else {}
        f2 = formatted_map(j1728map[0]) if j1728map else {}
        f = {}
        f["degree"] = jmaps[0]["degree"]
        f["domain_model_type"] = jmaps[0]["domain_model_type"]
        f["codomain_model_type"] = 1
        f["codomain_label"] = "1.1.0.1"
        f["codomain_name"] = "X(1)"
        f["codomain_equation"] = ""
        nb_coords = 0
        f["coord_names"] = []
        f["equations"] = []
        if jmap:
            nb_coords += 1
            f["equations"] += f1["equations"]
        if j1728map:
            nb_coords += 1
            cst = "1728"
            lead = j1728map[0]["leading_coefficients"]
            if lead is None:
                lead = ["1","1"]
            else:
                lead = lead[0]
            if not(int(lead[0]) < 0 and int(lead[1]) == 1):
                cst += "+"
            f["equations"] += [cst + f2["equations"][0]]
        if self.display_E4E6(domain_model_type):
            nb_coords += 1
            f["equations"] += [r"1728\,\frac{E_4^3}{E_4^3-E_6^2}"]
        f["nb_coords"] = nb_coords
        f["coord_names"] = ["j"] + [""]*(nb_coords-1)
        return(f)

    def formatted_E4E6(self, domain_model_type):
        E4E6 = [m for m in self.modelmaps_to_display if m["codomain_label"] == "1.1.0.1" and m["codomain_model_type"] == 4 and m["domain_model_type"] == domain_model_type][0]
        f = formatted_map(E4E6)
        f["coord_names"] = ["E_4", "E_6"]
        return(f)

    @lazy_attribute
    def formatted_jmaps(self):
        maps = []
        for domain_model_type in [0,1,2]:
            if self.display_j(domain_model_type):
                maps.append(self.formatted_jmap(domain_model_type))
            if self.display_E4E6(domain_model_type):
                maps.append(self.formatted_E4E6(domain_model_type))
        return maps

    @lazy_attribute
    def other_formatted_maps(self):
        maps = [m for m in self.modelmaps_to_display if m["codomain_label"] != "1.1.0.1"]
        codomain_labels = [m["codomain_label"] for m in maps]
        codomains = list(db.gps_gl2zhat_test.search(
            {"label": {"$in": codomain_labels}},
            ["label","name"]))
        # Do not display maps for which the codomain model has dont_display = False
        image_eqs = list(db.modcurve_models.search(
            {"modcurve": {"$in": codomain_labels},
             "dont_display": False},
            ["modcurve", "model_type", "equation"]))
        res = []
        for m in maps:
            codomain = [crv for crv in codomains if crv["label"] == m["codomain_label"]][0]
            codomain_name = codomain["name"]
            image_eq = [model for model in image_eqs
                        if model["modcurve"] == m["codomain_label"]
                        and model["model_type"] == m["codomain_model_type"]]
            if len(image_eq) > 0:
                codomain_equation = image_eq[0]["equation"]
                res.append(formatted_map(m, codomain_name=codomain_name,
                                         codomain_equation=codomain_equation))
        return res

    @lazy_attribute
    def all_formatted_maps(self):
        maps = self.formatted_jmaps + self.other_formatted_maps
        return [(m["degree"], m["domain_model_type"], m["codomain_label"], m["codomain_model_type"], m["codomain_name"], m["codomain_equation"], list(range(m["nb_coords"])), m["coord_names"], m["equations"]) for m in maps]

    @lazy_attribute
    def modelmaps_count(self):
        return db.modcurve_modelmaps.count({"domain_label": self.label})

    @lazy_attribute
    def has_more_modelmaps(self):
        return len(self.modelmaps_to_display) < self.modelmaps_count

    def cyclic_isogeny_field_degree(self):
        return min(r[1] for r in self.isogeny_orbits if r[0] == self.level)

    def cyclic_torsion_field_degree(self):
        return min(r[1] for r in self.orbits if r[0] == self.level)

    def full_torsion_field_degree(self):
        N = self.level
        P = integer_prime_divisors(N)
        GL2size = euler_phi(N) * N * (N // prod(P))**2 * prod(p**2 - 1 for p in P)
        return GL2size // self.index

    def show_generators(self):
        return ", ".join(r"$\begin{bmatrix}%s&%s\\%s&%s\end{bmatrix}$" % tuple(g) for g in self.generators)

    @lazy_attribute
    def modular_covers(self):
        curves = self.table.search({"label":{"$in": self.parents}}, ["label", "level", "index", "psl2index", "genus", "name", "rank", "dims"])
        return [(
            C["label"],
            name_to_latex(C["name"]) if C.get("name") else C["label"],
            C["level"],
            self.index // C["index"], # relative index
            self.psl2index // C["psl2index"], # relative degree
            C["genus"],
            C.get("rank", ""),
            formatted_dims(difference(self.dims, C.get("dims",[]))))
                for C in curves]

    @lazy_attribute
    def modular_covered_by(self):
        curves = self.table.search({"parents":{"$contains": self.label}}, ["label", "level", "index", "psl2index", "genus", "name", "rank", "dims"])
        return [(
            C["label"],
            name_to_latex(C["name"]) if C.get("name") else C["label"], # display name
            C["level"],
            C["index"] // self.index, # relative index
            C["psl2index"] // self.psl2index, # relative degree
            C["genus"],
            C.get("rank", ""),
            formatted_dims(difference(C.get("dims",[]), self.dims)))
                for C in curves]

    @lazy_attribute
    def fiber_product_of(self):
        curves = self.table.search({"label": {"$in": self.factorization, "$not": self.label}}, ["label", "level", "index", "psl2index", "genus", "name", "rank", "dims"])
        return [(
            C["label"],
            name_to_latex(C["name"]) if C.get("name") else C["label"],
            C["level"],
            self.index // C["index"], # relative index
            self.psl2index // C["psl2index"], # relative degree
            C["genus"],
            C.get("rank", ""),
            formatted_dims(difference(self.dims, C.get("dims",[]))))
                for C in curves]

    @lazy_attribute
    def newform_level(self):
        return lcm([int(f.split('.')[0]) for f in self.newforms])

    @lazy_attribute
    def downloads(self):
        self.downloads = [
            (
                "Code to Magma",
                url_for(".modcurve_magma_download", label=self.label),
            ),
            (
                "Code to SageMath",
                url_for(".modcurve_sage_download", label=self.label),
            ),
            (
                "All data to text",
                url_for(".modcurve_text_download", label=self.label),
            ),
            (
                'Underlying data',
                url_for(".modcurve_data", label=self.label),
            )

        ]
        #self.downloads.append(("Underlying data", url_for(".belyi_data", label=self.label)))
        return self.downloads

    @lazy_attribute
    def known_degree1_points(self):
        return db.modcurve_points.count({"curve_label": self.label, "degree": 1})

    @lazy_attribute
    def known_degree1_noncm_points(self):
        return db.modcurve_points.count({"curve_label": self.label, "degree": 1, "cm": 0})

    @lazy_attribute
    def known_low_degree_points(self):
        return db.modcurve_points.count({"curve_label": self.label, "degree": {"$gt": 1}})

    @lazy_attribute
    def db_rational_points(self):
        # Use the db.ec_curvedata table to automatically find rational points
        limit = None if (self.genus > 1 or self.genus == 1 and self.rank == 0) else 10
        if ZZ(self.level).is_prime_power():
            search_noncm = db.ec_curvedata.search(
                {"elladic_images": {"$contains": self.label}, "cm": 0},
                sort=["conductor", "iso_nlabel", "lmfdb_number"],
                one_per=["jinv"],
                limit=limit,
                projection=["lmfdb_label", "ainvs", "jinv", "cm"])
            search_cm = db.ec_curvedata.search(
                {"elladic_images": {"$contains": self.label}, "cm": {"$ne": 0}},
                sort=["conductor", "iso_nlabel", "lmfdb_number"],
                one_per=["jinv"],
                limit=None,
                projection=["lmfdb_label", "ainvs", "jinv", "cm", "conductor", "iso_nlabel", "lmfdb_number"])
            curves = list(search_noncm) + list(search_cm)
            curves.sort(key=lambda x: (x["conductor"], x["iso_nlabel"], x["lmfdb_number"]))
            return [(rec["lmfdb_label"], url_for_EC_label(rec["lmfdb_label"]), EC_equation(rec["ainvs"]), "no" if rec["cm"] == 0 else f'${rec["cm"]}$', showj(rec["jinv"]), showj_fac(rec["jinv"]))
                    for rec in curves]
        else:
            return []

    @lazy_attribute
    def db_nf_points(self):
        pts = []
        for rec in db.modcurve_points.search(
                {"curve_label": self.label, "degree": {"$gt": 1}},
                sort=["degree"],
                projection=["Elabel","cm","isolated","jinv","j_field",
                            "jorig","residue_field","degree"]):
            pts.append(
                (rec["Elabel"],
                 url_for_ECNF_label(rec["Elabel"]) if rec["Elabel"] else "",
                 "no" if rec["cm"] == 0 else f'${rec["cm"]}$',
                 "yes" if rec["isolated"] is True else ("no" if rec["isolated"] is False else "maybe"),
                 showj_nf(rec["jinv"], rec["j_field"], rec["jorig"], rec["residue_field"]),
                 rec["residue_field"],
                 url_for_NF_label(rec["residue_field"]),
                 rec["j_field"],
                 url_for_NF_label(rec["j_field"]),
                 rec["degree"]))
        return pts

    @lazy_attribute
    def old_db_nf_points(self):
        # Use the db.ec_curvedata table to automatically find rational points
        #limit = None if (self.genus > 1 or self.genus == 1 and self.rank == 0) else 10
        if ZZ(self.level).is_prime():
            curves = list(db.ec_nfcurves.search(
                {"galois_images": {"$contains": self.Slabel},
                 "degree": {"$lte": self.genus}},
                one_per=["jinv"],
                projection=["label", "degree", "equation", "jinv", "cm"]))
            Ra = PolynomialRing(QQ,'a')
            return [(rec["label"],
                     url_for_ECNF_label(rec["label"]),
                     rec["equation"],
                     "no" if rec["cm"] == 0 else f'${rec["cm"]}$',
                     "yes" if (rec["degree"] < ZZ(self.gonality_bounds[0]) / 2 or rec["degree"] < self.gonality_bounds[0] and (self.rank == 0 or self.simple and rec["degree"] < self.genus)) else "maybe",
                     web_latex(Ra([QQ(s) for s in rec["jinv"].split(',')]))) for rec in curves]
        else:
            return []

    @lazy_attribute
    def rational_points_description(self):
        curve = self
        if curve.known_degree1_noncm_points or curve.pointless == -1:
            if curve.genus == 0 or (curve.genus == 1 and curve.rank > 0):
                if curve.level == 1:
                    return r'This modular curve has infinitely many rational points, corresponding to <a href="%s&all=1">elliptic curves over $\Q$</a>.' % url_for('ec.rational_elliptic_curves')
                elif curve.known_degree1_points > 0:
                    return 'This modular curve has infinitely many rational points, including <a href="%s">%s</a>.' % (
                        url_for('.low_degree_points', curve=curve.label, degree=1),
                        pluralize(curve.known_degree1_points, "stored non-cuspidal point"))
                else:
                    return r'This modular curve has infinitely many rational points but none with conductor small enough to be contained within the <a href="%s">database of elliptic curves over $\Q$</a>.' % url_for('ec.rational_elliptic_curves')
            elif curve.genus > 1 or (curve.genus == 1 and curve.rank == 0):
                if curve.rational_cusps and curve.cm_discriminants and curve.known_degree1_noncm_points > 0:
                    return 'This modular curve has rational points, including %s, %s and <a href="%s">%s</a>.' % (
                        pluralize(curve.rational_cusps, "rational cusp"),
                        pluralize(len(curve.cm_discriminants), "rational CM point"),
                        url_for('.low_degree_points', curve=curve.label, degree=1, cm='noCM'),
                        pluralize(curve.known_degree1_noncm_points, "known non-cuspidal non-CM point"))
                elif curve.rational_cusps and curve.cm_discriminants:
                    return 'This modular curve has %s and %s, but no other known rational points.' % (
                        pluralize(curve.rational_cusps, "rational cusp"),
                        pluralize(len(curve.cm_discriminants), "rational CM point"))
                elif curve.rational_cusps and curve.known_degree1_noncm_points > 0:
                    return 'This modular curve has rational points, including %s and <a href="%s">%s</a>.' % (
                        pluralize(curve.rational_cusps, "rational_cusp"),
                        url_for('.low_degree_points', curve=curve.label, degree=1, cm='noCM'),
                        pluralize(curve.known_degree1_noncm_points, "known non-cuspidal non-CM point"))
                elif curve.cm_discriminants and curve.known_degree1_noncm_points > 0:
                    return 'This modular curve has rational points, including %s and <a href="%s">%s</a>, but no rational cusps.' % (
                        pluralize(len(curve.cm_discriminants), "rational CM point"),
                        url_for('.low_degree_points', curve=curve.label, degree=1, cm='noCM'),
                        pluralize(curve.known_degree1_noncm_points, "known non-cuspidal non-CM point"))
                elif curve.rational_cusps:
                    return 'This modular curve has %s but no known non-cuspidal rational points.' % (
                        pluralize(curve.rational_cusps, "rational cusp"))
                elif curve.cm_discriminants:
                    return 'This modular curve has %s but no rational cusps or other known rational points.' % (
                        pluralize(len(curve.cm_discriminants), "rational CM point"))
                elif curve.known_degree1_points > 0:
                    return 'This modular curve has <a href="%s">%s</a> but no rational cusps or CM points.' % (
                        url_for('.low_degree_points', curve=curve.label, degree=1),
                        pluralize(curve.known_degree1_points, "known rational point"))
        else:
            if curve.obstructions == [0]:
                return 'This modular curve has no real points, and therefore no rational points.'
            elif 0 in curve.obstructions:
                return fr'This modular curve has no real points and no $\Q_p$ points for $p={curve.obstruction_primes}$, and therefore no rational points.'
            elif curve.obstructions:
                return fr'This modular curve has no $\Q_p$ points for $p={curve.obstruction_primes}$, and therefore no rational points.'
            elif curve.pointless == 0:
                if curve.genus <= 90:
                    pexp = "$p$ not dividing the level"
                else:
                    pexp = "good $p < 8192"
                return fr'This modular curve has real points and $\Q_p$ points for {pexp}, but no known rational points.'
            elif curve.genus > 1 or (curve.genus == 1 and curve.rank == 0):
                return "This modular curve has finitely many rational points, none of which are cusps."
