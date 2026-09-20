"""Gera o site estático da Magitronic em docs/ (servido pelo GitHub Pages).

Uso:
  python tools/build.py                   # ambiente de homologação (magitronic.borzanti.com, noindex)
  python tools/build.py --env production  # versão final para www.magitronic.com.br

Somente biblioteca padrão. Fontes do conteúdo:
  src/site.json            dados da empresa (telefone, endereço, horário, avaliações…)
  src/services/*.json      páginas de serviço e de peças (um arquivo por URL)
  src/pages/*.html         páginas avulsas com cabeçalho "---" (home, contato, orçamento…)
  src/blog/*.html          artigos do blog com cabeçalho "---"
  src/templates/*.html     layout, cabeçalho e rodapé
  src/assets/              CSS, JS e imagens (copiados para docs/assets)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "docs"

esc = html.escape


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


class Site:
    def __init__(self, env: str, theme: str = "a", prefix: str = ""):
        self.env = env
        self.staging = env == "staging"
        self.theme = theme          # "a" = versão original, "b" = versão de mais impacto visual
        self.prefix = prefix        # ex.: "/v2" — publica a variante numa subpasta
        self.d = json.loads(read(SRC / "site.json"))
        self.base = self.d["production_url"]
        self.images = json.loads(read(SRC / "assets" / "img" / "manifest.json"))
        self.services = [json.loads(read(p)) for p in sorted((SRC / "services").glob("*.json"))]
        self.services.sort(key=lambda s: s.get("order", 99))
        self.by_slug = {s["slug"]: s for s in self.services}
        self.posts = []
        for p in sorted((SRC / "blog").glob("*.html")):
            meta, body = parse_front_matter(read(p))
            meta["slug"] = p.stem
            meta["body"] = body
            self.posts.append(meta)
        self.posts.sort(key=lambda m: m["date"], reverse=True)
        self.asset_version = self._asset_hash()
        self.pages: list[dict] = []

    # ---------- utilidades ----------
    def _asset_hash(self) -> str:
        h = hashlib.md5()
        for p in sorted((SRC / "assets").rglob("*")):
            if p.is_file() and p.suffix in (".css", ".js"):
                h.update(p.read_bytes())
        return h.hexdigest()[:8]

    def url(self, path: str) -> str:
        return self.base + path

    def public_url(self, path: str) -> str:
        """Endereço onde a página está de fato publicada. Em homologação é o domínio de
        demonstração; é o que as prévias de link (WhatsApp, redes) precisam alcançar."""
        base = self.d["staging_url"] if self.staging else self.base
        return base + (self.prefix if path != "/" or self.prefix else "") + ("" if path == "/" and not self.prefix else path).replace("//", "/")

    def wa(self, msg: str | None = None) -> str:
        return f"https://wa.me/{self.d['whatsapp_number']}?text={quote(msg or self.d['whatsapp_default_msg'])}"

    def img(self, name: str, alt: str, cls: str = "", eager: bool = False, sizes: str = "") -> str:
        w, h = self.images[name]
        loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
        c = f' class="{cls}"' if cls else ""
        s = f' sizes="{sizes}"' if sizes else ""
        return (f'<img src="/assets/img/{name}.webp" width="{w}" height="{h}" alt="{esc(alt)}"'
                f'{c}{s} {loading} decoding="async">')

    # ---------- componentes reutilizáveis ----------
    def wa_button(self, msg: str | None = None, label: str = "Chamar no WhatsApp", cls: str = "btn btn-wa") -> str:
        return (f'<a class="{cls}" href="{esc(self.wa(msg))}" target="_blank" rel="noopener" data-track="whatsapp">'
                f'{ICON_WA}<span>{esc(label)}</span></a>')

    def phone_link(self, cls: str = "") -> str:
        c = f' class="{cls}"' if cls else ""
        return f'<a{c} href="tel:{self.d["phone_e164"]}" data-track="phone">{self.d["phone_display"]}</a>'

    def brand_chips(self) -> str:
        return '<ul class="chips" aria-label="Marcas atendidas">' + "".join(
            f"<li>{esc(b)}</li>" for b in self.d["brands"]) + "</ul>"

    def reviews(self) -> str:
        items = "".join(
            f'<figure class="review"><div class="stars" aria-hidden="true">★★★★★</div>'
            f'<blockquote>{esc(r["text"])}</blockquote><figcaption>{esc(r["name"])}</figcaption></figure>'
            for r in self.d["reviews"])
        return (f'<div class="reviews">{items}</div>'
                f'<p class="reviews-more"><a href="{esc(self.d["reviews_url"])}" target="_blank" rel="noopener">'
                f'Ver todas as avaliações no Google →</a></p>')

    def steps(self) -> str:
        steps = [
            ("Conte o problema", "Pelo WhatsApp ou pelo formulário: marca, modelo e o que está acontecendo. Fotos ajudam."),
            ("Diagnóstico grátis", "Um técnico avalia o notebook na loja e identifica a causa, sem compromisso."),
            ("Você aprova o orçamento", "Enviamos o valor e o prazo por escrito. Só fazemos o reparo com a sua autorização."),
            ("Reparo com garantia", "Você retira o notebook testado, com garantia de 90 dias sobre o serviço."),
        ]
        return '<ol class="steps">' + "".join(
            f'<li><h3>{esc(t)}</h3><p>{esc(d)}</p></li>' for t, d in steps) + "</ol>"

    def service_cards(self, kind: str = "all", exclude: str = "", limit: int = 0) -> str:
        items = [s for s in self.services if (kind == "all" or s["kind"] == kind) and s["slug"] != exclude]
        if limit:
            items = items[:limit]
        cards = "".join(
            f'<li><a class="card-link" href="/{s["slug"]}">'
            f'<span class="card-title">{esc(s["nav_label"])}</span>'
            f'<span class="card-text">{esc(s["card"])}</span></a></li>'
            for s in items)
        cls = "cards cards-3" if kind == "peca" else "cards"
        return f'<ul class="{cls}">{cards}</ul>'

    def related(self, slugs: list[str]) -> str:
        cards = "".join(
            f'<li><a class="card-link" href="/{s}"><span class="card-title">{esc(self.by_slug[s]["nav_label"])}</span>'
            f'<span class="card-text">{esc(self.by_slug[s]["card"])}</span></a></li>'
            for s in slugs if s in self.by_slug)
        return f'<ul class="cards cards-3">{cards}</ul>'

    def select(self, name: str, label: str, options: list[str], selected: str = "", required: bool = False,
               fid: str = "") -> str:
        fid = fid or f"f-{name}"
        opts = '<option value="">Selecione</option>' + "".join(
            f'<option{" selected" if o == selected else ""}>{esc(o)}</option>' for o in options)
        req = " required" if required else ""
        return (f'<div class="field"><label for="{fid}">{esc(label)}</label>'
                f'<select id="{fid}" name="{name}" data-label="{esc(label)}"{req}>{opts}</select></div>')

    def field(self, name: str, label: str, type_: str = "text", required: bool = False, placeholder: str = "",
              autocomplete: str = "", fid: str = "", hint: str = "") -> str:
        fid = fid or f"f-{name}"
        req = " required" if required else ""
        ph = f' placeholder="{esc(placeholder)}"' if placeholder else ""
        ac = f' autocomplete="{autocomplete}"' if autocomplete else ""
        inputmode = ' inputmode="tel"' if type_ == "tel" else ""
        opt = "" if required else ' <span class="opt">(opcional)</span>'
        h = f'<small class="hint">{esc(hint)}</small>' if hint else ""
        if type_ == "textarea":
            ctrl = f'<textarea id="{fid}" name="{name}" rows="4" data-label="{esc(label)}"{req}{ph}></textarea>'
        else:
            ctrl = (f'<input id="{fid}" name="{name}" type="{type_}" data-label="{esc(label)}"'
                    f'{req}{ph}{ac}{inputmode}>')
        return f'<div class="field"><label for="{fid}">{esc(label)}{opt}</label>{ctrl}{h}</div>'

    def consent(self, fid: str) -> str:
        return (f'<div class="field check"><input id="{fid}" name="consentimento" type="checkbox" required>'
                f'<label for="{fid}">Autorizo a Magitronic a usar estes dados para responder meu pedido, '
                f'conforme a <a href="/politica-de-privacidade">política de privacidade</a>.</label></div>')

    def form_wrap(self, inner: str, fid: str, intro: str, subject: str, channel: str, button: str,
                  note: str = "") -> str:
        key = esc(self.d["web3forms_key"])
        n = f'<p class="form-note">{note}</p>' if note else ""
        return (f'<form class="lead-form" id="{fid}" data-lead-form data-channel="{channel}" '
                f'data-intro="{esc(intro)}" data-subject="{esc(subject)}" data-key="{key}" '
                f'data-wa="{self.d["whatsapp_number"]}" novalidate>'
                f'{inner}'
                f'<input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">'
                f'<button class="btn btn-wa btn-block" type="submit">{ICON_WA}<span>{esc(button)}</span></button>'
                f'<p class="form-status" role="status" aria-live="polite"></p>{n}</form>')

    def quick_form(self, defeito: str = "", inline: bool = False) -> str:
        """Orçamento rápido: só marca, modelo e defeito, direto para o WhatsApp.

        inline=True usa a barra horizontal que fica sob o topo da home."""
        fields = (self.select("marca", "Marca", self.d["brands"] + ["Outra"], fid="q-marca")
                  + self.field("modelo", "Modelo", required=False, placeholder="Ex.: Inspiron 15 3520", fid="q-modelo")
                  + self.select("defeito", "O que está acontecendo?", DEFEITOS, selected=defeito, required=True,
                                fid="q-defeito"))
        inner = fields if inline else (
            '<div class="grid-2">'
            + self.select("marca", "Marca", self.d["brands"] + ["Outra"], fid="q-marca")
            + self.field("modelo", "Modelo", required=False, placeholder="Ex.: Inspiron 15 3520", fid="q-modelo")
            + "</div>"
            + self.select("defeito", "O que está acontecendo?", DEFEITOS, selected=defeito, required=True,
                          fid="q-defeito"))
        form = self.form_wrap(inner, "quick-form", "Olá! Quero um orçamento para o meu notebook.",
                              "Orçamento rápido (site)", "whatsapp",
                              "Receber orçamento" if inline else "Receber orçamento no WhatsApp",
                              "" if inline else "Resposta em horário comercial. Sem cadastro.")
        return form.replace('class="lead-form"', 'class="lead-form lead-form-inline"', 1) if inline else form

    def service_links(self) -> str:
        """Lista compacta de todos os serviços e peças (substitui a grade de 18 cartões na home)."""
        def col(kind: str, titulo: str) -> str:
            items = "".join(f'<li><a href="/{s["slug"]}">{esc(s["nav_label"])}</a></li>'
                            for s in self.services if s["kind"] == kind)
            return f'<div><p class="group-title">{titulo}</p><ul class="dir-list">{items}</ul></div>'
        return f'<div class="directory">{col("servico", "Consertos")}{col("peca", "Peças com instalação")}</div>' 

    def short_form(self, defeito: str = "", tipo: str = "Conserto", intro: str = "") -> str:
        inner = ('<div class="grid-2">'
                 + self.field("nome", "Seu nome", required=True, autocomplete="name", fid="s-nome")
                 + self.field("whatsapp", "WhatsApp", "tel", required=True, placeholder="(11) 90000-0000",
                              autocomplete="tel", fid="s-whats")
                 + self.select("marca", "Marca", self.d["brands"] + ["Outra"], fid="s-marca")
                 + self.field("modelo", "Modelo", placeholder="Ex.: IdeaPad 3 15ITL6", fid="s-modelo")
                 + "</div>"
                 + self.select("defeito", "Defeito", DEFEITOS, selected=defeito, required=True, fid="s-defeito")
                 + self.field("descricao", "Descreva o problema", "textarea", fid="s-desc")
                 + f'<input type="hidden" name="tipo" value="{esc(tipo)}" data-label="Tipo">'
                 + self.consent("s-consent"))
        return self.form_wrap(inner, "short-form", intro or "Olá! Quero um orçamento.",
                              f"Pedido de orçamento — {tipo}", "whatsapp", "Enviar e abrir o WhatsApp")

    def part_form(self, peca: str = "") -> str:
        inner = (self.select("peca", "Peça", PECAS, selected=peca, required=True, fid="p-peca")
                 + '<div class="grid-2">'
                 + self.select("marca", "Marca do notebook", self.d["brands"] + ["Outra"], required=True, fid="p-marca")
                 + self.field("modelo", "Modelo ou part number", required=True, placeholder="Ex.: Dell Vostro 3510",
                              fid="p-modelo", hint="Fica na etiqueta embaixo do notebook.")
                 + self.field("nome", "Seu nome", required=True, autocomplete="name", fid="p-nome")
                 + self.field("whatsapp", "WhatsApp", "tel", required=True, placeholder="(11) 90000-0000",
                              autocomplete="tel", fid="p-whats")
                 + "</div>"
                 + self.select("instalacao", "Precisa de instalação?", ["Sim, instalar na loja", "Não, só a peça"],
                               fid="p-inst")
                 + '<input type="hidden" name="tipo" value="Peça" data-label="Tipo">'
                 + self.consent("p-consent"))
        return self.form_wrap(inner, "part-form", "Olá! Quero consultar a disponibilidade de uma peça.",
                              "Consulta de peça (site)", "whatsapp", "Consultar disponibilidade")

    def full_form(self) -> str:
        inner = ('<fieldset><legend>Seus dados</legend><div class="grid-2">'
                 + self.field("nome", "Nome", required=True, autocomplete="name", fid="o-nome")
                 + self.field("whatsapp", "WhatsApp ou telefone", "tel", required=True,
                              placeholder="(11) 90000-0000", autocomplete="tel", fid="o-whats")
                 + self.field("email", "E-mail", "email", autocomplete="email", fid="o-email")
                 + '<div class="field"><span class="label" id="o-pref-l">Prefiro resposta por</span>'
                   '<div class="radios" role="radiogroup" aria-labelledby="o-pref-l">'
                   '<label><input type="radio" name="preferencia" value="WhatsApp" data-label="Resposta por" checked> WhatsApp</label>'
                   '<label><input type="radio" name="preferencia" value="Ligação" data-label="Resposta por"> Ligação</label>'
                   '<label><input type="radio" name="preferencia" value="E-mail" data-label="Resposta por"> E-mail</label>'
                   '</div></div>'
                 + '</div></fieldset>'
                 + '<fieldset><legend>Seu notebook</legend><div class="grid-2">'
                 + self.select("tipo", "Você precisa de", ["Conserto", "Peça", "Recuperação de dados", "Upgrade"],
                               required=True, fid="o-tipo")
                 + self.select("marca", "Marca", self.d["brands"] + ["Outra"], required=True, fid="o-marca")
                 + self.field("modelo", "Modelo", placeholder="Ex.: Acer Aspire 5 A515-54", fid="o-modelo",
                              hint="Fica na etiqueta embaixo do notebook.")
                 + self.select("defeito", "Defeito principal", DEFEITOS, required=True, fid="o-defeito")
                 + '</div>'
                 + self.field("descricao", "Conte o que aconteceu", "textarea",
                              placeholder="Ex.: caiu da mesa, a tela ficou com listras e depois apagou.", fid="o-desc")
                 + '<p class="hint">Tem fotos? Depois de enviar, mande pelo WhatsApp — ajudam no orçamento.</p>'
                 + '</fieldset>'
                 + self.consent("o-consent"))
        return self.form_wrap(inner, "full-form", "Olá! Quero um orçamento.", "Pedido de orçamento (site)",
                              "auto", "Enviar pedido de orçamento")

    def render_quem_somos(self) -> str:
        """Imagem do bloco "Quem somos": recortada nas versões claras, com o fundo
        original na versão C, onde a transparência não funciona (o render é claro)."""
        alt = ("Notebook aberto com telas de diagnóstico, engrenagens, escudo e nuvem flutuando ao "
               "redor, e a placa com a marca Magitronic")
        nome = "notebook-render-fundo" if self.theme == "c" else "notebook-render"
        return f'<figure class="figure-frame">{self.img(nome, alt)}</figure>'

    def map_block(self, facade: bool = False) -> str:
        """Mapa do Google. Com facade=True o iframe (~1 MB de scripts) só carrega quando a pessoa clica."""
        a = self.d["address"]
        title = f'Mapa: {esc(a["street"])}, {esc(a["district"])}'
        src = esc(self.d["maps_embed"])
        if facade:
            return (f'<div class="map map-facade"><button type="button" class="map-load" data-map-src="{src}" '
                    f'data-map-title="{title}"><span class="map-pin" aria-hidden="true"></span>'
                    f'<strong>{esc(a["street"])}</strong><span>{esc(a["district"])} · {esc(a["city"])}</span>'
                    f'<span class="btn btn-primary btn-sm">Ver no mapa</span></button></div>')
        return (f'<div class="map"><iframe title="{title}" src="{src}" loading="lazy" '
                f'referrerpolicy="no-referrer-when-downgrade"></iframe></div>')

    def info_address(self) -> str:
        """Endereço da barra do topo: completo no desktop, curto no celular, sempre com link para o mapa."""
        a = self.d["address"]
        longo = f'{a["street"]} — {a["district"]}, {a["state"]}'
        curto = f'{a["district"]}, {a["city"]}'
        return (f'<a class="info-place" href="{esc(self.d["maps_url"])}" target="_blank" rel="noopener" data-track="maps">'
                f'{ICON_PIN}<span class="so-largo">{esc(longo)}</span><span class="so-estreito">{esc(curto)}</span></a>')

    def info_hours(self) -> str:
        return (f'{ICON_CLOCK}<span class="so-largo">{esc(self.d["hours_display"])}</span>'
                f'<span class="so-estreito">{esc(self.d["hours_short"])}</span>')

    def address_html(self) -> str:
        a = self.d["address"]
        return (f'<address>{esc(a["street"])}<br>{esc(a["district"])} · {esc(a["city"])} – {esc(a["state"])}'
                f'<br>CEP {esc(a["zip"])}</address>')

    def blog_list(self, limit: int = 0) -> str:
        posts = self.posts[:limit] if limit else self.posts
        items = "".join(
            f'<li><a class="card-link" href="/blog/{p["slug"]}"><span class="card-meta">{fmt_date(p["date"])}</span>'
            f'<span class="card-title">{esc(p["title"])}</span><span class="card-text">{esc(p["description"])}</span></a></li>'
            for p in posts)
        return f'<ul class="cards cards-2">{items}</ul>'

    def faq(self, items: list[dict]) -> str:
        return '<div class="faq">' + "".join(
            f'<details><summary>{esc(i["q"])}</summary><div>{i["a"]}</div></details>' for i in items) + "</div>"

    # ---------- tokens {{ nome:arg }} usados nas páginas ----------
    def expand(self, text: str) -> str:
        def repl(m: re.Match) -> str:
            name, arg = m.group(1), (m.group(2) or "").strip()
            if name in COMPONENTS:
                return COMPONENTS[name](self, arg)
            if name in self.d and isinstance(self.d[name], str):
                return esc(self.d[name])
            raise KeyError(f"token desconhecido: {name}")
        return re.sub(r"\{\{\s*([a-z_]+)(?::([^}]*))?\s*\}\}", repl, text)

    # ---------- schema.org ----------
    def local_business(self) -> dict:
        a = self.d["address"]
        return {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "@id": self.url("/#empresa"),
            "name": self.d["legal_name"],
            "alternateName": self.d["name"],
            "url": self.url("/"),
            "logo": self.url("/assets/img/logo-magitronic.png"),
            "image": self.url("/assets/img/og-magitronic.jpg"),
            "telephone": self.d["phone_e164"],
            "email": self.d["email"],
            "foundingDate": self.d["founded"],
            "address": {"@type": "PostalAddress", "streetAddress": a["street"], "addressLocality": a["city"],
                        "addressRegion": a["state"], "postalCode": a["zip"], "addressCountry": "BR"},
            "geo": {"@type": "GeoCoordinates", "latitude": a["lat"], "longitude": a["lng"]},
            "openingHoursSpecification": [
                {"@type": "OpeningHoursSpecification", "dayOfWeek": h["days"], "opens": h["opens"],
                 "closes": h["closes"]} for h in self.d["hours_schema"]],
            "areaServed": ["Moema", "Vila Olímpia", "Indianópolis", "Ibirapuera", "Brooklin", "Campo Belo",
                           "Vila Mariana", "Zona Sul de São Paulo"],
            "sameAs": [self.d["instagram"]],
            "contactPoint": {"@type": "ContactPoint", "telephone": "+55" + self.d["whatsapp_number"][2:],
                             "contactType": "customer service", "availableLanguage": "Portuguese"},
        }

    def breadcrumb_schema(self, trail: list[tuple[str, str]]) -> dict:
        return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": self.url(u)} for i, (n, u) in enumerate(trail)]}

    def faq_schema(self, items: list[dict]) -> dict:
        return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": i["q"],
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", i["a"])}} for i in items]}

    # ---------- montagem da página ----------
    def add(self, **page) -> None:
        self.pages.append(page)

    def render(self, page: dict) -> str:
        path = page["url"]
        trail = page.get("trail") or []
        schemas = list(page.get("schema", []))
        if trail:
            schemas.append(self.breadcrumb_schema([("Início", "/")] + trail))
        ld = "".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>'
                     for s in schemas)
        robots = "noindex, nofollow" if (self.staging or page.get("noindex") or self.prefix) else "index, follow"
        canonical = self.url(path) if path != "/404" else ""
        og_base = self.d["staging_url"] if self.staging else self.base
        og_image = og_base + "/assets/img/og-magitronic.jpg"
        og_url = og_base + (self.prefix or "") + ("/" if path == "/" else path)
        preload = ""
        if page.get("preload"):
            preload = f'<link rel="preload" as="image" href="/assets/img/{page["preload"]}.webp" fetchpriority="high">'
        # versões A e B são claras, C é escura: declarar evita o modo escuro automático do Chrome
        esquema = "dark" if self.theme == "c" else "light"
        head = "\n".join(filter(None, [
            f'<title>{esc(page["title"])}</title>',
            f'<meta name="color-scheme" content="{esquema}">',
            f'<meta name="description" content="{esc(page["description"])}">',
            f'<meta name="robots" content="{robots}">',
            f'<link rel="canonical" href="{canonical}">' if canonical else "",
            f'<meta property="og:type" content="{page.get("og_type", "website")}">',
            f'<meta property="og:locale" content="pt_BR">',
            f'<meta property="og:site_name" content="Magitronic">',
            f'<meta property="og:title" content="{esc(page["title"])}">',
            f'<meta property="og:description" content="{esc(page["description"])}">',
            f'<meta property="og:url" content="{og_url}">',
            f'<meta property="og:image" content="{og_image}">',
            f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
            f'<meta name="twitter:card" content="summary_large_image">',
            preload,
            ld,
        ]))
        crumbs = ""
        if trail:
            links = '<li><a href="/">Início</a></li>' + "".join(
                (f'<li><a href="{u}">{esc(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{esc(n)}</li>')
                for i, (n, u) in enumerate(trail))
            crumbs = f'<nav class="breadcrumb wrap" aria-label="Você está em"><ol>{links}</ol></nav>'
        tpl = self.templates
        demo = self.demo_bar() if self.staging else ""
        gtm_head = gtm_body = ""
        if self.d["gtm_id"]:
            gid = self.d["gtm_id"]
            gtm_head = GTM_HEAD.replace("GTM_ID", gid)
            gtm_body = GTM_BODY.replace("GTM_ID", gid)
        out = (tpl["base"]
               .replace("[[head]]", head)
               .replace("[[gtm_head]]", gtm_head)
               .replace("[[gtm_body]]", gtm_body)
               .replace("[[demo]]", demo)
               .replace("[[header]]", self.header(path))
               .replace("[[breadcrumb]]", crumbs)
               .replace("[[content]]", page["body"])
               .replace("[[footer]]", tpl["footer"])
               .replace("[[body_attrs]]", self.body_attrs())
               .replace("[[theme_css]]", self.theme_css())
               .replace("[[v]]", self.asset_version))
        out = self.expand(out)
        if self.prefix:
            # links e ações internos passam a apontar para a subpasta (os assets continuam na raiz)
            out = re.sub(r'(href|src|action)="/(?!/|assets/)', lambda m: f'{m.group(1)}="{self.prefix}/', out)
        return out.replace('href="@@', 'href="')

    def body_attrs(self) -> str:
        attrs = f' data-base="{self.prefix}"' if self.prefix else ""
        return f' class="theme-{self.theme}"{attrs}' if self.theme != "a" else attrs

    def theme_css(self) -> str:
        if self.theme == "a":
            return ""
        extra = ""
        if self.theme == "c":  # a versão C usa uma fonte monoespaçada nos rótulos técnicos
            extra = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                     'family=IBM+Plex+Mono:wght@400;600&display=swap">')
        return f'{extra}<link rel="stylesheet" href="/assets/css/theme-{self.theme}.css?v={self.asset_version}">'

    #: tema -> (rótulo, caminho em homologação)
    VERSOES = {"a": ("A · clássica", "/"), "b": ("B · impacto", "/v2/"), "c": ("C · tech", "/v3/")}

    def demo_bar(self) -> str:
        """Barra de protótipo com o seletor entre as versões visuais."""
        # "@@" protege estes links da reescrita de prefixo feita em render()
        links = "".join(
            f'<a href="@@{path}" class="ver-{t}{" atual" if t == self.theme else ""}">{esc(label)}</a>'
            for t, (label, path) in self.VERSOES.items())
        return (self.templates["demo-bar"]
                .replace("[[switch]]", links)
                .replace("[[atual]]", self.theme.upper()))

    def header(self, path: str) -> str:
        def links(kind: str) -> str:
            return "".join(
                f'<li><a href="/{s["slug"]}"{" aria-current=\"page\"" if path == "/" + s["slug"] else ""}>'
                f'{esc(s["nav_label"])}</a></li>'
                for s in self.services if s["kind"] == kind)
        return (self.templates["header"]
                .replace("[[nav_consertos]]", links("servico"))
                .replace("[[nav_pecas]]", links("peca")))

    @property
    def templates(self) -> dict:
        if not hasattr(self, "_tpl"):
            self._tpl = {p.stem: read(p) for p in (SRC / "templates").glob("*.html")}
        return self._tpl


# ---------- listas compartilhadas ----------
DEFEITOS = [
    "Não liga ou desliga sozinho",
    "Tela quebrada, piscando ou sem imagem",
    "Teclado ou touchpad falhando",
    "Bateria ou carregamento",
    "Esquentando ou fazendo barulho",
    "Lento ou travando",
    "Caiu líquido ou sofreu queda",
    "Recuperação de dados",
    "Upgrade (SSD ou memória)",
    "Outro",
]
PECAS = ["Tela", "Teclado", "Bateria", "Carregador / fonte", "Memória RAM", "SSD", "Cooler", "Outra peça"]

ICON_PIN = ('<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 '
            '5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z"/></svg>')
ICON_CLOCK = ('<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 '
              '10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm1-13h-2v6l5 3 1-1.7-4-2.3Z"/></svg>')
ICON_WA = ('<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 '
           '15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2c-1.5 0-3-.4-4.3-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c'
           '-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8'
           'c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5'
           '-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3Z"/></svg>')

GTM_HEAD = ("<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});"
            "var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;"
            "j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);"
            "})(window,document,'script','dataLayer','GTM_ID');</script>")
GTM_BODY = ('<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM_ID" height="0" width="0" '
            'style="display:none;visibility:hidden"></iframe></noscript>')

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def fmt_date(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} de {MESES[m - 1]} de {y}"


def _wa_url(site: Site, arg: str) -> str:
    return esc(site.wa(arg or None))


def _wa_button(site: Site, arg: str) -> str:
    msg, _, label = arg.partition("|")
    return site.wa_button(msg or None, label or "Chamar no WhatsApp")


COMPONENTS = {
    "wa_url": _wa_url,
    "wa_button": _wa_button,
    "phone_link": lambda s, a: s.phone_link(a),
    "phone_href": lambda s, a: f"tel:{s.d['phone_e164']}",
    "address": lambda s, a: s.address_html(),
    "info_address": lambda s, a: s.info_address(),
    "info_hours": lambda s, a: s.info_hours(),
    "hours": lambda s, a: esc(s.d["hours_display"]),
    "brands": lambda s, a: s.brand_chips(),
    "reviews": lambda s, a: s.reviews(),
    "steps": lambda s, a: s.steps(),
    "service_cards": lambda s, a: s.service_cards(a or "all"),
    "quick_form": lambda s, a: s.quick_form("" if a == "inline" else a, inline=(a == "inline")),
    "service_links": lambda s, a: s.service_links(),
    "short_form": lambda s, a: s.short_form(a),
    "part_form": lambda s, a: s.part_form(a),
    "full_form": lambda s, a: s.full_form(),
    "map": lambda s, a: s.map_block(facade=(a == "facade")),
    "img_quem_somos": lambda s, a: s.render_quem_somos(),
    "blog_list": lambda s, a: s.blog_list(int(a) if a else 0),
    "img": lambda s, a: s.img(*[x.strip() for x in a.split("|")][:2]),
    "img_hero": lambda s, a: s.img(*[x.strip() for x in a.split("|")][:2], eager=True),
    "sitemap_links": lambda s, a: s.sitemap_links(),
    "year": lambda s, a: str(date.today().year),
    "anos": lambda s, a: str(date.today().year - int(s.d["founded"])),   # anos de casa, sempre atual
    "maps_url": lambda s, a: esc(s.d["maps_url"]),
    "instagram_url": lambda s, a: esc(s.d["instagram"]),
    "email_link": lambda s, a: f'<a href="mailto:{s.d["email"]}">{s.d["email"]}</a>',
}


# ---------- página de serviço / peça ----------
def render_service(site: Site, s: dict) -> str:
    is_part = s["kind"] == "peca"
    facts = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in s["facts"])
    highlights = "".join(f"<li>{esc(h)}</li>" for h in s["highlights"])
    symptoms = "".join(f'<li><h3>{esc(x["t"])}</h3><p>{esc(x["d"])}</p></li>' for x in s["symptoms"])
    sections = "".join(f'<section class="prose"><h2>{esc(x["h2"])}</h2>{x["html"]}</section>' for x in s["sections"])
    form = site.part_form(s.get("form_peca", "")) if is_part else site.short_form(
        s.get("form_defeito", ""), intro=f"Olá! Quero um orçamento de {s['nav_label'].lower()}.")
    form_title = "Consulte a peça para o seu modelo" if is_part else f"Peça o orçamento de {s['nav_label'].lower()}"
    cta_label = "Consultar peça no WhatsApp" if is_part else "Chamar no WhatsApp"
    return f"""
<section class="page-hero">
  <div class="wrap page-hero-grid">
    <div class="page-hero-text">
      <p class="eyebrow">{"Peças para notebook" if is_part else "Conserto de notebook"} · Moema, SP</p>
      <h1>{esc(s["h1"])}</h1>
      <p class="lead">{esc(s["lead"])}</p>
      <ul class="ticks">{highlights}</ul>
      <div class="actions">
        {site.wa_button(s["wa_msg"], cta_label)}
        <a class="btn btn-ghost" href="#orcamento">{"Consultar pelo formulário" if is_part else "Pedir orçamento"}</a>
      </div>
    </div>
    <figure class="page-hero-img">{site.img(s["image"], s["image_alt"], eager=True, sizes="(min-width: 900px) 440px, 100vw")}</figure>
  </div>
</section>

<section class="wrap section">
  <h2>{esc(s["symptoms_title"])}</h2>
  <ul class="symptoms">{symptoms}</ul>
</section>

<div class="wrap two-col">
  <div class="main-col">
    {sections}
    <section class="prose">
      <h2>Marcas atendidas</h2>
      {site.brand_chips()}
    </section>
  </div>
  <aside class="side-col">
    <div class="facts-box">
      <h2 class="h4">Resumo</h2>
      <dl class="facts">{facts}</dl>
      <p class="facts-note">Valores e prazos confirmados no orçamento, após o diagnóstico.</p>
    </div>
  </aside>
</div>

<section class="band" id="orcamento">
  <div class="wrap band-grid">
    <div>
      <h2>{esc(form_title)}</h2>
      <p>Preencha em menos de um minuto. O pedido chega no nosso WhatsApp e respondemos em horário comercial.</p>
      <p class="band-alt">Prefere ligar? {site.phone_link()}</p>
    </div>
    {form}
  </div>
</section>

<section class="wrap section">
  <h2>Perguntas frequentes</h2>
  {site.faq(s["faq"])}
</section>

<section class="wrap section">
  <h2>{"Outras peças e serviços" if is_part else "Serviços relacionados"}</h2>
  {site.related(s["related"])}
</section>
"""


def sitemap_links(self: Site) -> str:
    cons = "".join(f'<li><a href="/{s["slug"]}">{esc(s["nav_label"])}</a></li>'
                   for s in self.services if s["kind"] == "servico")
    pec = "".join(f'<li><a href="/{s["slug"]}">{esc(s["nav_label"])}</a></li>'
                  for s in self.services if s["kind"] == "peca")
    posts = "".join(f'<li><a href="/blog/{p["slug"]}">{esc(p["title"])}</a></li>' for p in self.posts)
    inst = "".join(f'<li><a href="{u}">{n}</a></li>' for n, u in [
        ("Início", "/"), ("Pedir orçamento", "/orcamento"), ("Todos os serviços", "/servicos"),
        ("Peças para notebook", "/pecas-para-notebook"), ("Assistência técnica em Moema", "/assistencia-tecnica-notebook-moema"),
        ("Quem somos", "/quem-somos"), ("Contato", "/contato"), ("Blog", "/blog/"),
        ("Política de privacidade", "/politica-de-privacidade")])
    return (f'<div class="sitemap-cols"><div><h2 class="h4">Institucional</h2><ul>{inst}</ul></div>'
            f'<div><h2 class="h4">Consertos</h2><ul>{cons}</ul></div>'
            f'<div><h2 class="h4">Peças</h2><ul>{pec}</ul></div>'
            f'<div><h2 class="h4">Blog</h2><ul>{posts}</ul></div></div>')


Site.sitemap_links = sitemap_links


def out_file(path: str, out_dir: Path = OUT) -> Path:
    if path == "/":
        return out_dir / "index.html"
    if path.endswith("/"):
        return out_dir / path.strip("/") / "index.html"
    return out_dir / (path.strip("/") + ".html")


def build(env: str, theme: str = "a", prefix: str = "", out_dir: Path | None = None,
          clean: bool = True) -> Site:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    out_dir = out_dir or OUT
    site = Site(env, theme=theme, prefix=prefix)

    # páginas de serviço e peças
    for s in site.services:
        group = ("Peças", "/pecas-para-notebook") if s["kind"] == "peca" else ("Serviços", "/servicos")
        svc_schema = {
            "@context": "https://schema.org", "@type": "Service", "name": s["h1"], "description": s["description"],
            "serviceType": s["nav_label"], "url": site.url("/" + s["slug"]),
            "provider": {"@id": site.url("/#empresa")},
            "areaServed": {"@type": "City", "name": "São Paulo"},
        }
        site.add(url="/" + s["slug"], title=s["title"], description=s["description"],
                 body=render_service(site, s), trail=[group, (s["nav_label"], "/" + s["slug"])],
                 schema=[svc_schema, site.faq_schema(s["faq"])], preload=s["image"], priority="0.8")

    # páginas avulsas
    for p in sorted((SRC / "pages").glob("*.html")):
        meta, body = parse_front_matter(read(p))
        trail = []
        if meta.get("breadcrumb"):
            trail = [(meta["breadcrumb"], meta["url"])]
        schema = [site.local_business()] if meta.get("schema") == "localbusiness" else []
        site.add(url=meta["url"], title=meta["title"], description=meta["description"], body=body, trail=trail,
                 schema=schema, noindex=meta.get("noindex") == "true", preload=meta.get("preload"),
                 priority=meta.get("priority", "0.6"))

    # blog
    for post in site.posts:
        article = {
            "@context": "https://schema.org", "@type": "BlogPosting", "headline": post["title"],
            "description": post["description"], "datePublished": post["date"],
            "dateModified": post.get("updated", post["date"]),
            "image": site.url(f"/assets/img/{post['image']}.webp"),
            "author": {"@type": "Organization", "name": "Equipe técnica Magitronic"},
            "publisher": {"@id": site.url("/#empresa")},
            "mainEntityOfPage": site.url(f"/blog/{post['slug']}"),
        }
        body = f"""
<article class="wrap post">
  <header class="post-head">
    <p class="eyebrow"><time datetime="{post["date"]}">{fmt_date(post["date"])}</time> · Equipe técnica Magitronic</p>
    <h1>{esc(post["title"])}</h1>
    <p class="lead">{esc(post["description"])}</p>
  </header>
  <figure class="post-img">{site.img(post["image"], post["image_alt"], eager=True)}</figure>
  <div class="prose">{post["body"]}</div>
  <aside class="post-cta">
    <h2 class="h3">Seu notebook está com esse problema?</h2>
    <p>Diagnóstico grátis na loja em Moema. Conte o que está acontecendo e respondemos com o próximo passo.</p>
    <div class="actions">{{{{wa_button:{post.get("wa_msg", "")}|Falar com um técnico}}}}<a class="btn btn-ghost" href="/orcamento">Pedir orçamento</a></div>
  </aside>
</article>"""
        title = f"{post['title']} | Magitronic"
        if len(title) > 65:  # o Google corta títulos longos; nesse caso fica só o título do artigo
            title = post["title"]
        site.add(url=f"/blog/{post['slug']}", title=title, description=post["description"],
                 body=body, trail=[("Blog", "/blog/"), (post["title"], f"/blog/{post['slug']}")],
                 schema=[article], og_type="article", preload=post["image"], priority="0.5")

    # saída
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    if clean:
        shutil.copytree(SRC / "assets", out_dir / "assets", ignore=shutil.ignore_patterns("manifest.json"))
    for page in site.pages:
        write(out_file(page["url"], out_dir), site.render(page))

    if prefix:
        print(f"{len(site.pages)} páginas geradas em {out_dir} (versão {theme.upper()})")
        return site

    urls = [p for p in site.pages if not p.get("noindex") and p["url"] != "/404"]
    today = date.today().isoformat()
    sm = "".join(f"<url><loc>{site.url(p['url'])}</loc><lastmod>{today}</lastmod><priority>{p['priority']}</priority></url>\n"
                 for p in sorted(urls, key=lambda p: p["url"]))
    write(OUT / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}</urlset>\n')
    if site.staging:
        write(OUT / "robots.txt", "# Homologação: todas as páginas levam <meta name=\"robots\" content=\"noindex\">.\n"
              "User-agent: *\nAllow: /\n")
        write(OUT / "CNAME", site.d["staging_cname"] + "\n")
    else:
        write(OUT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site.url('/sitemap.xml')}\n")
    write(OUT / ".nojekyll", "")
    print(f"{len(site.pages)} páginas geradas em {OUT} (ambiente: {env})")
    return site


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=["staging", "production"], default="staging")
    ap.add_argument("--theme", choices=["a", "b", "c"], default="a", help="versão visual publicada na raiz")
    ap.add_argument("--no-variant", action="store_true", help="não gerar a segunda versão em /v2")
    args = ap.parse_args()
    build(args.env, theme=args.theme)
    if args.env == "staging" and not args.no_variant:
        for t, (_, path) in Site.VERSOES.items():
            if t == args.theme:
                continue
            sub = path.strip("/")
            build(args.env, theme=t, prefix="/" + sub, out_dir=OUT / sub, clean=False)
