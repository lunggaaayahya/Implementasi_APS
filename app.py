"""Implementasi US1-US9 (Quiz) dengan database SQLite.
Jalankan: python app.py  ->  http://127.0.0.1:5000
Database dibuat otomatis (quiz2.db). Hapus file itu untuk mengembalikan data contoh ke awal."""
import calendar, os, random, sqlite3
from contextlib import closing
from datetime import date
from flask import Flask, request, redirect, session, render_template, flash, abort
from jinja2 import DictLoader

app = Flask(__name__); app.secret_key = "dev-quiz2"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz2.db")
TH, JATAH = 2026, 12
MON = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]

# ===== Skema database (mengikuti domain model Sistem A dan Sistem B) =====
SCHEMA = """
CREATE TABLE IF NOT EXISTS pegawai(id INTEGER PRIMARY KEY, nama TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cuti(id INTEGER PRIMARY KEY AUTOINCREMENT, pegawai_id INTEGER NOT NULL REFERENCES pegawai(id),
  mulai TEXT NOT NULL, selesai TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('diajukan','disetujui')));
CREATE TABLE IF NOT EXISTS bandara(kode TEXT PRIMARY KEY, kota TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maskapai(id INTEGER PRIMARY KEY, nama TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS jadwal(id INTEGER PRIMARY KEY, asal TEXT NOT NULL REFERENCES bandara(kode), tujuan TEXT NOT NULL REFERENCES bandara(kode),
  tanggal TEXT NOT NULL, jam TEXT NOT NULL, maskapai_id INTEGER NOT NULL REFERENCES maskapai(id), harga INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pengunjung(id INTEGER PRIMARY KEY, nama TEXT NOT NULL, email TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS profil_member(id INTEGER PRIMARY KEY CHECK(id=1), nama TEXT NOT NULL DEFAULT '', nik TEXT NOT NULL DEFAULT '',
  hp TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', lahir TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS pemesanan(ref TEXT PRIMARY KEY, pemilik TEXT NOT NULL, pengunjung_id INTEGER REFERENCES pengunjung(id),
  penumpang TEXT NOT NULL, jadwal_id INTEGER NOT NULL REFERENCES jadwal(id),
  status TEXT NOT NULL CHECK(status IN ('booked','waiting for payment','confirmed','dibatalkan')), valid INTEGER NOT NULL DEFAULT 0,
  dibuat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS etiket(id INTEGER PRIMARY KEY AUTOINCREMENT, pengunjung_id INTEGER NOT NULL REFERENCES pengunjung(id),
  ref TEXT NOT NULL REFERENCES pemesanan(ref), subjek TEXT NOT NULL, isi TEXT NOT NULL);
"""
def Q(sql, a=()):
    with closing(sqlite3.connect(DB)) as c:
        c.row_factory = sqlite3.Row
        return c.execute(sql, a).fetchall()
def ex(sql, a=()):
    with closing(sqlite3.connect(DB)) as c:
        c.execute("PRAGMA foreign_keys=ON"); cur = c.execute(sql, a); c.commit(); return cur.lastrowid

JSEL = "SELECT j.id, j.asal AS o, j.tujuan AS d, j.tanggal AS date, j.jam AS time, m.nama AS air, j.harga AS price FROM jadwal j JOIN maskapai m ON m.id=j.maskapai_id"
BSEL = "SELECT ref, pemilik AS owner, pengunjung_id AS vis, penumpang AS pax, jadwal_id AS f, status, valid FROM pemesanan"
fl = lambda i: (Q(JSEL + " WHERE j.id=?", (i,)) or [None])[0]
ap = lambda: {r["kode"]: r["kota"] for r in Q("SELECT * FROM bandara ORDER BY rowid")}
vis_map = lambda: {r["id"]: (r["nama"], r["email"]) for r in Q("SELECT * FROM pengunjung ORDER BY id")}
def profil(): r = Q("SELECT nama,nik,hp,email,lahir FROM profil_member WHERE id=1")[0]; return {k: r[k] for k in r.keys()}
def days(s, e): return (date.fromisoformat(e) - date.fromisoformat(s)).days + 1

def add(ref, owner, vis, pax, f, status):   # simpan Pemesanan; bila untuk pengunjung, terbitkan ETiket (UC-B12)
    ex("INSERT INTO pemesanan(ref,pemilik,pengunjung_id,penumpang,jadwal_id,status) VALUES(?,?,?,?,?,?)", (ref, owner, vis or None, pax, f, status))
    if vis:
        x, k, v = fl(f), ap(), vis_map()[vis]
        ex("INSERT INTO etiket(pengunjung_id,ref,subjek,isi) VALUES(?,?,?,?)", (vis, ref, "E-tiket " + ref,
           f"{pax}: {k[x['o']]} ke {k[x['d']]}, {x['date']} {x['time']}, {x['air']}. Dikirim ke {v[1]}."))
    return ref
def new_booking(owner, vis, pax, f):
    return add("".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6)), owner, vis, pax, f, "booked")

def init_db():
    with closing(sqlite3.connect(DB)) as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM pegawai").fetchone()[0]: return
        c.executemany("INSERT INTO pegawai VALUES(?,?)", [(1,"Ayu Lestari"),(2,"Bagas Pratama"),(3,"Citra Dewi"),(4,"Dimas Saputra"),(5,"Eka Wulandari")])
        c.executemany("INSERT INTO cuti(pegawai_id,mulai,selesai,status) VALUES(?,?,?,?)", [
            (1,"2026-03-02","2026-03-04","disetujui"),(1,"2026-08-17","2026-08-21","disetujui"),(1,"2026-11-23","2026-11-27","diajukan"),
            (2,"2026-01-12","2026-01-14","disetujui"),(2,"2026-12-21","2026-12-31","diajukan"),(3,"2026-05-04","2026-05-08","disetujui"),
            (3,"2026-11-25","2026-11-26","diajukan"),(3,"2026-12-01","2026-12-03","diajukan"),(4,"2026-06-15","2026-06-19","disetujui"),
            (4,"2026-12-24","2026-12-26","diajukan"),(5,"2025-12-22","2025-12-26","disetujui"),(5,"2026-11-30","2026-12-02","diajukan")])
        AP = [("CGK","Jakarta"),("SUB","Surabaya"),("MLG","Malang"),("DPS","Denpasar"),("YIA","Yogyakarta")]
        AIR = [("Garuda Indonesia",1.4),("Citilink",1.0),("Lion Air",0.8)]
        DT = ["2026-11-20","2026-11-21","2026-11-22","2026-11-23"]; TM = ["06:10","11:40","15:25","19:50"]
        c.executemany("INSERT INTO bandara VALUES(?,?)", AP)
        c.executemany("INSERT INTO maskapai VALUES(?,?)", [(i + 1, a[0]) for i, a in enumerate(AIR)])
        rows = []
        for i, a in enumerate(AP):
            for j, b in enumerate(AP):
                if i == j: continue
                base = 420000 + ((i*7 + j*13) % 9) * 55000
                for k, d in enumerate(DT):
                    for m, t in enumerate(TM):
                        x = (i + j + k + m) % 3
                        rows.append((len(rows), a[0], b[0], d, t, x + 1, round(base*AIR[x][1]*(1 + k*.03 - (.05 if m == 3 else 0))/1000)*1000))
        c.executemany("INSERT INTO jadwal VALUES(?,?,?,?,?,?,?)", rows)
        c.executemany("INSERT INTO pengunjung VALUES(?,?,?)", [(1,"Rina Maharani","rina@mail.id"),(2,"Fajar Nugroho","fajar@mail.id")])
        c.execute("INSERT INTO profil_member(id,nama) VALUES(1,'Member Demo')")   # sisanya sengaja kosong
        c.commit()
    add("GA7K2Q","manajer",1,"Rina Maharani",5,"confirmed"); add("CT4M9X","manajer",2,"Fajar Nugroho",140,"waiting for payment")
    add("LN3R8P","user",0,"Pengguna Umum",60,"booked"); add("GA5T6W","member",0,"Member Demo",200,"booked")

ROLES = {"user":("Pengguna",["cari","multi","batal"]),
         "member":("Member Frequent Traveller",["cari","multi","banding","md","profil","validasi","batal"]),
         "manajer":("Manajer Travel",["status","pesanvis","otor"]), "visitor":("Pengunjung",["tiket","email"])}
LBL = dict(cari="Cari jadwal", multi="Beberapa tujuan", batal="Pesanan saya", banding="Bandingkan", md="Multi-destinasi", profil="Profil",
           validasi="Validasi tiket", status="Status booking", pesanvis="Pesan untuk pengunjung", otor="Otorisasi", tiket="Tiket saya", email="Kotak masuk e-tiket")
rp = lambda n: "Rp" + f"{n:,}".replace(",", ".")
def hour_ok(t, w): h = int(t[:2]); return not w or (w == "p" and h < 11) or (w == "s" and 11 <= h < 16) or (w == "m" and h >= 16)
def find(o="", d="", dt="", w=""):
    rows = Q(JSEL + " WHERE (?='' OR j.asal=?) AND (?='' OR j.tujuan=?) AND (?='' OR j.tanggal=?) ORDER BY j.tanggal, j.jam, j.id", (o, o, d, d, dt, dt))
    return [f for f in rows if hour_ok(f["time"], w)]
role = lambda: session.get("role", "user")

@app.context_processor
def ctx():
    parts = request.path.strip("/").split("/")
    return dict(role=role(), ROLES=ROLES, LBL=LBL, AP=ap(), DTP=[(r[0], r[0]) for r in Q("SELECT DISTINCT tanggal FROM jadwal ORDER BY 1")],
                fl=fl, rp=rp, MON=MON, VIS=vis_map(), tab=parts[1] if len(parts) > 1 else "", sysb=parts[0] == "b", chip=lambda s: s.split()[0])

# ===== Sistem A: UC-A01..A03 =====
@app.route("/")
def home(): return redirect("/a")

@app.route("/a")
def a():
    y, m, d = request.args.get("y", TH, int), request.args.get("m", 11, int), request.args.get("d", "")
    last = calendar.monthrange(y, m)[1]; bad = bool(d) and int(d) > last
    s, e = (f"{y}-{m:02d}-{int(d):02d}",) * 2 if d else (f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last:02d}")
    rows = [] if bad else Q("SELECT pegawai_id,mulai,selesai,status FROM cuti WHERE mulai<=? AND selesai>=? ORDER BY mulai", (e, s))
    p, detail = request.args.get("p", type=int), None
    if p:
        r = Q("SELECT pegawai_id,mulai,selesai,status FROM cuti WHERE pegawai_id=? ORDER BY mulai DESC", (p,))
        detail = dict(r=r, used=sum(days(c[1], c[2]) for c in r if c[3] == "disetujui" and c[1].startswith(str(TH))))
    PEG = {r["id"]: r["nama"] for r in Q("SELECT * FROM pegawai")}
    return render_template("a.html", rows=rows, y=y, m=m, d=d, bad=bad, p=p, detail=detail, PEG=PEG, days=days, JATAH=JATAH, TH=TH)

# ===== Sistem B =====
@app.route("/role/<r>")
def set_role(r):
    if r not in ROLES: abort(404)
    session["role"] = r; return redirect("/b/" + ROLES[r][1][0])

@app.route("/b/<tab>")
def search(tab):
    if tab not in ("cari", "multi", "md", "banding", "pesanvis", "tiket", "email", "status", "otor", "profil", "validasi", "batal"): abort(404)
    if tab in ("tiket", "email"):
        vid = request.args.get("vis", session.get("vis", 1), int); session["vis"] = vid
        return render_template("visitor.html", vid=vid, bs=Q(BSEL + " WHERE pengunjung_id=? ORDER BY rowid", (vid,)),
                               em=Q("SELECT subjek AS subj, isi AS body FROM etiket WHERE pengunjung_id=? ORDER BY id", (vid,)))
    if tab == "status":
        st = request.args.get("st", ""); return render_template("status.html", st=st, bs=Q(BSEL + " WHERE (?='' OR status=?) ORDER BY rowid", (st, st)))
    if tab == "otor":
        kode = request.args.get("kode", "").strip().upper(); found = (Q(BSEL + " WHERE ref=?", (kode,)) or [None])[0]
        if kode and not found: flash("Kode booking reference tidak sesuai. Masukkan ulang kode booking reference.", "err")
        return render_template("otor.html", kode=kode, b=found)
    if tab == "profil": return render_template("profil.html", P=profil())
    if tab in ("validasi", "batal"):
        return render_template("bookings.html", bs=Q(BSEL + " WHERE pemilik=? AND status!='dibatalkan' ORDER BY rowid", (role(),)), full=all(profil().values()))
    q, groups, a = request.args, None, request.args
    if a.get("go"):
        if tab in ("multi", "md"):
            ds = a.getlist("ds")
            if len(ds) < 2: flash("Pilih minimal dua tujuan.", "err")
            elif tab == "md" and not (a.get("o") and a.get("date")): flash("Pilih lokasi keberangkatan dan tanggal.", "err")
            else: groups = [(g, find(a.get("o", ""), g, a.get("date", ""))) for g in ds]
        elif not a.get("d"): flash("Pilih tujuan terlebih dahulu.", "err")
        elif tab == "banding" and not a.get("date"): flash("Pilih tujuan dan tanggal.", "err")
        else:
            l = find(a.get("o", ""), a["d"], a.get("date", ""), a.get("w", ""))
            groups = [("", sorted(l, key=lambda f: f["price"]) if tab == "banding" else l)]
    return render_template("search.html", q=q, ds=a.getlist("ds"), groups=groups, best=(min(f["price"] for f in groups[0][1]) if tab == "banding" and groups and groups[0][1] else 0))

@app.route("/b/pesan/<int:fid>", methods=["GET", "POST"])    # UC-B03 dan UC-B10
def pesan(fid):
    f = fl(fid) or abort(404); m = role() == "manajer"
    if request.method == "POST":
        vis = int(request.form.get("vis", 0)) if m else 0
        pax = vis_map()[vis][0] if m else request.form.get("pax", "").strip()
        if not pax: flash("Isi nama penumpang.", "err"); return redirect(request.url)
        ref = new_booking(role(), vis, pax, fid)
        flash(f"Pemesanan berhasil. Kode booking reference: {ref}." + (f" E-tiket dikirim ke {vis_map()[vis][1]}." if m else ""), "ok")
        return redirect("/b/status" if m else "/b/batal")
    return render_template("pesan.html", f=f)

@app.post("/b/act/<what>/<ref>")
def act(what, ref):
    if not Q("SELECT 1 FROM pemesanan WHERE ref=?", (ref,)): abort(404)
    if what == "batal": ex("UPDATE pemesanan SET status='dibatalkan' WHERE ref=?", (ref,)); flash(f"Pesanan {ref} dibatalkan.", "ok")
    elif what == "otor":
        ex("UPDATE pemesanan SET status='confirmed' WHERE ref=?", (ref,)); flash(f"Tiket {ref} berhasil diotorisasi. Status booking: confirmed.", "ok"); return redirect(f"/b/otor?kode={ref}")
    elif what == "validasi":   # UC-B07
        if not all(profil().values()): flash("Data profil tidak lengkap. Validasi tiket ditolak sampai profil dilengkapi.", "err")
        else: ex("UPDATE pemesanan SET valid=1 WHERE ref=?", (ref,)); flash(f"Tiket {ref} tervalidasi dengan data profil {profil()['nama']}.", "ok")
    return redirect(request.referrer or "/b/batal")

@app.post("/b/profil")   # UC-B06
def save_profil():
    f = request.form; ex("UPDATE profil_member SET nama=?, nik=?, hp=?, email=?, lahir=? WHERE id=1", tuple(f.get(k, "").strip() for k in ("nama", "nik", "hp", "email", "lahir")))
    flash("Data profil tersimpan.", "ok"); return redirect("/b/profil")

T = {}
T["base.html"] = """<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quiz</title>
<style>body{font:15px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:16px;background:#eef1f4;color:#14213d}
nav a{display:inline-block;padding:6px 12px;margin:0 6px 6px 0;border:1px solid #cbd3dd;border-radius:999px;background:#fff;color:inherit;text-decoration:none}nav a.on{background:#14213d;color:#fff}
main{background:#fff;border:1px solid #d6dce4;border-radius:12px;padding:16px;overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid #e1e6ec;white-space:nowrap}
.ok{color:#17703f}.err{color:#b42318}.best td{background:#e2f4ea}.chip{padding:1px 8px;border-radius:999px;background:#e3f1f6;font-size:.8rem}.chip.confirmed,.chip.disetujui{background:#e2f4ea;color:#17703f}.chip.waiting,.chip.diajukan{background:#fdf0dc;color:#9a4a07}.chip.dibatalkan{background:#fde8e6;color:#b42318}
label{display:inline-block;margin:0 10px 8px 0;font-size:.85rem}input,select,button{font:inherit;padding:6px 8px}fieldset{display:inline-block}.card{border:1px solid #d6dce4;border-radius:8px;padding:10px;margin-bottom:8px}</style>
<h1>Implementasi User Story, Quiz</h1>
<nav><a class="{{'on' if not sysb}}" href="/a">Sistem A: Monitoring cuti</a><a class="{{'on' if sysb}}" href="/role/{{role}}">Sistem B: Pemesanan tiket</a></nav>
{% if sysb %}<nav>{% for k,v in ROLES.items() %}<a class="{{'on' if role==k}}" href="/role/{{k}}">{{v[0]}}</a>{% endfor %}</nav>
<nav>{% for t in ROLES[role][1] %}<a class="{{'on' if tab==t}}" href="/b/{{t}}">{{LBL[t]}}</a>{% endfor %}</nav>{% endif %}
<main>{% for c,m in get_flashed_messages(with_categories=true) %}<p class="{{c}}"><b>{{m}}</b></p>{% endfor %}{% block c %}{% endblock %}</main></html>"""
T["a.html"] = """{% extends "base.html" %}{% block c %}<p>UC-A01 sampai A03 (US1).</p>
<form>Tanggal <select name=d onchange="this.form.submit()"><option value="">Semua</option>{% for i in range(1,32) %}<option {{'selected' if d|string==i|string}}>{{i}}</option>{% endfor %}</select>
Bulan <select name=m onchange="this.form.submit()">{% for n in MON %}<option value="{{loop.index}}" {{'selected' if m==loop.index}}>{{n}}</option>{% endfor %}</select>
Tahun <select name=y onchange="this.form.submit()">{% for i in (2025,2026,2027) %}<option {{'selected' if y==i}}>{{i}}</option>{% endfor %}</select></form>
{% if bad %}<p class=err>Tanggal tidak ada pada bulan ini.</p>{% elif rows %}<table><tr><th>Pegawai</th><th>Periode</th><th>Lama</th><th>Status</th></tr>
{% for c in rows %}<tr><td><a href="?d={{d}}&m={{m}}&y={{y}}&p={{c[0]}}">{{PEG[c[0]]}}</a></td><td>{{c[1]}} s.d. {{c[2]}}</td><td>{{days(c[1],c[2])}} hari</td><td><span class="chip {{c[3]}}">{{c[3]}}</span></td></tr>{% endfor %}</table>
{% else %}<p>Tidak ada pengajuan cuti pada periode ini.</p>{% endif %}
{% if detail %}<h3>{{PEG[p]}}: riwayat dan sisa cuti {{TH}}</h3><p>Jatah {{JATAH}} hari, terpakai {{detail.used}}, <b>sisa {{JATAH-detail.used}} hari</b>.</p>
<table>{% for c in detail.r %}<tr><td>{{c[1]}} s.d. {{c[2]}}</td><td>{{days(c[1],c[2])}} hari</td><td><span class="chip {{c[3]}}">{{c[3]}}</span></td></tr>{% endfor %}</table>{% endif %}{% endblock %}"""
T["search.html"] = """{% extends "base.html" %}
{% macro sel(n,l,items,all) %}<label>{{l}} <select name="{{n}}"><option value="">{{all}}</option>{% for k,v in items %}<option value="{{k}}" {{'selected' if q.get(n)==k}}>{{v}}</option>{% endfor %}</select></label>{% endmacro %}
{% macro flights(l,best) %}{% if not l %}<p>Belum ada penerbangan sesuai pilihan.</p>{% else %}<table><tr><th>Tanggal</th><th>Jam</th><th>Rute</th><th>Maskapai</th><th>Harga</th><th></th></tr>
{% for f in l[:24] %}<tr class="{{'best' if best and f.price==best}}"><td>{{f.date}}</td><td>{{f.time}}</td><td>{{AP[f.o]}} ke {{AP[f.d]}}</td><td>{{f.air}}</td><td>{{rp(f.price)}}{% if best %} {{'(termurah)' if f.price==best else '+'~rp(f.price-best)}}{% endif %}</td>
<td><a href="/b/pesan/{{f.id}}">{{'Pesan untuk pengunjung' if role=='manajer' else 'Pesan'}}</a></td></tr>{% endfor %}</table>{% endif %}{% endmacro %}
{% block c %}<form><input type=hidden name=go value=1>
{% if tab in ('multi','md') %}{{sel('o','Asal',AP.items(),'Pilih' if tab=='md' else 'Semua')}}{{sel('date','Tanggal',DTP,'Pilih' if tab=='md' else 'Semua')}}
<fieldset><legend>Tujuan</legend>{% for k,v in AP.items() %}<label><input type=checkbox name=ds value="{{k}}" {{'checked' if k in ds}}> {{v}}</label>{% endfor %}</fieldset>
{% else %}{{sel('d','Tujuan',AP.items(),'Pilih tujuan')}}{{sel('o','Asal',AP.items(),'Semua')}}{{sel('date','Tanggal',DTP,'Semua')}}
{% if tab=='banding' %}{{sel('w','Jam',[('p','Pagi'),('s','Siang'),('m','Malam')],'Semua jam')}}{% endif %}{% endif %}
<button>Cari</button></form><br>
{% if groups is not none %}{% if tab=='md' %}<table><tr><th>Tujuan</th><th>Jumlah</th><th>Termurah</th><th>Rata-rata</th></tr>{% for g,l in groups %}<tr><td>{{AP[g]}}</td><td>{{l|length}}</td><td>{{rp(l|map(attribute='price')|min) if l else '-'}}</td><td>{{rp((l|sum(attribute='price')/l|length)|round|int) if l else '-'}}</td></tr>{% endfor %}</table>{% endif %}
{% for g,l in groups %}{% if g %}<h4>{{AP[g]}} ({{l|length}})</h4>{% endif %}{{flights(l,best)}}{% endfor %}{% endif %}{% endblock %}"""
T["pesan.html"] = """{% extends "base.html" %}{% block c %}<div class=card><b>{{AP[f.o]}} ke {{AP[f.d]}}</b><br>{{f.date}} {{f.time}}, {{f.air}}, {{rp(f.price)}}</div>
<form method=post>{% if role=='manajer' %}<label>Pengunjung <select name=vis>{% for k,v in VIS.items() %}<option value="{{k}}">{{v[0]}} ({{v[1]}})</option>{% endfor %}</select></label>
{% else %}<label>Nama penumpang <input name=pax></label>{% endif %}<button>Konfirmasi pemesanan</button></form>{% endblock %}"""
T["bookings.html"] = """{% extends "base.html" %}{% macro card(b) %}{% set f=fl(b.f) %}<div class=card><b>{{b.ref}}</b> <span class="chip {{chip(b.status)}}">{{b.status}}</span>{{' (tervalidasi)' if b.valid}}<br>{{b.pax}}: {{AP[f.o]}} ke {{AP[f.d]}}, {{f.date}} {{f.time}}, {{f.air}}, {{rp(f.price)}}{% endmacro %}
{% block c %}{% if tab=='validasi' %}<p>Status profil: {{'lengkap' if full else 'belum lengkap (isi di menu Profil)'}}</p>{% endif %}{% for b in bs %}{{card(b)}}
<form method=post action="/b/act/{{'validasi' if tab=='validasi' else 'batal'}}/{{b.ref}}">{% if tab=='validasi' %}{% if not b.valid %}<button>Validasi tiket</button>{% endif %}{% else %}<button>Batalkan tiket</button>{% endif %}</form></div>
{% else %}<p>Belum ada pesanan aktif.</p>{% endfor %}{% endblock %}"""
T["status.html"] = """{% extends "base.html" %}{% block c %}<form><select name=st onchange="this.form.submit()"><option value="">Semua status</option>{% for s in ('confirmed','booked','waiting for payment') %}<option {{'selected' if st==s}}>{{s}}</option>{% endfor %}</select></form>
<table><tr><th>Kode</th><th>Penumpang</th><th>Rute</th><th>Tanggal</th><th>Status</th></tr>{% for b in bs %}{% set f=fl(b.f) %}<tr><td>{{b.ref}}</td><td>{{b.pax}}</td><td>{{AP[f.o]}} ke {{AP[f.d]}}</td><td>{{f.date}}</td><td><span class="chip {{chip(b.status)}}">{{b.status}}</span></td></tr>{% endfor %}</table>{% endblock %}"""
T["otor.html"] = """{% extends "base.html" %}{% block c %}<form><label>Kode booking reference <input name=kode value="{{kode}}" placeholder="GA7K2Q"></label><button>Cek kode</button></form>
{% if b %}<div class=card><b>{{b.ref}}</b> <span class="chip {{chip(b.status)}}">{{b.status}}</span><br>{{b.pax}}</div>{% if b.status not in ('confirmed','dibatalkan') %}<form method=post action="/b/act/otor/{{b.ref}}"><button>Otorisasi tiket</button></form>{% endif %}{% endif %}{% endblock %}"""
T["profil.html"] = """{% extends "base.html" %}{% block c %}<form method=post>{% for k,v in P.items() %}<label>{{k}} <input name={{k}} value="{{v}}" {{'type=date' if k=='lahir'}}></label>{% endfor %}<button>Simpan profil</button></form>{% endblock %}"""
T["visitor.html"] = """{% extends "base.html" %}{% block c %}<form><select name=vis onchange="this.form.submit()">{% for k,v in VIS.items() %}<option value="{{k}}" {{'selected' if vid==k}}>{{v[0]}}</option>{% endfor %}</select></form><br>
{% if tab=='tiket' %}{% for b in bs %}{% set f=fl(b.f) %}<div class=card><b>{{b.ref}}</b> {{b.status}}<br>{{AP[f.o]}} ke {{AP[f.d]}}, {{f.date}} {{f.time}}, {{f.air}}</div>{% else %}<p>Belum ada tiket.</p>{% endfor %}
{% else %}{% for e in em %}<div class=card><b>{{e.subj}}</b><br>{{e.body}}</div>{% else %}<p>Belum ada e-tiket.</p>{% endfor %}{% endif %}{% endblock %}"""
app.jinja_loader = DictLoader(T)

init_db()
if __name__ == "__main__": app.run(debug=True)
