# Site Magitronic — protótipo

Nova versão do site da [Magitronic](https://www.magitronic.com.br) (assistência técnica de notebooks em Moema, SP), feita a partir da auditoria de SEO e conversão. É um site estático gerado por um script Python e publicado pelo GitHub Pages.

- **Homologação — versão A (clássica):** https://magitronic.borzanti.com
- **Homologação — versão B (impacto):** https://magitronic.borzanti.com/v2/ — azul-noite e âmbar
- **Homologação — versão C (tech):** https://magitronic.borzanti.com/v3/ — interface escura, ciano e rótulos monoespaçados
- **Produção (futuro):** https://www.magitronic.com.br

Em homologação todas as páginas têm `noindex`, e a barra do topo permite alternar entre as versões.

As versões A e B são **sempre claras**, mesmo com o aparelho em modo escuro: elas declaram `color-scheme: only light`. A versão C é escura por concepção. Navegadores que forçam o modo escuro em todos os sites, como o Samsung Internet com essa opção ligada, escurecem qualquer página e não podem ser contornados pelo site.

## Estrutura

```
src/
  site.json          dados da empresa: telefones, endereço, horário, avaliações, chave do Web3Forms
  services/*.json    uma página por serviço/peça (mesmas URLs do site atual)
  pages/*.html       páginas avulsas (home, orçamento, contato, peças, blog…)
  blog/*.html        artigos do blog
  templates/         layout, cabeçalho, rodapé e barra de protótipo
  assets/css/site.css     visual da versão A (base de tudo)
  assets/css/theme-b.css  camada da versão B, carregada depois da base
  assets/css/theme-c.css  camada da versão C (tema escuro "tech")
  assets/            CSS, JS e imagens otimizadas (WebP)
  img-original/      imagens originais do site atual (fora do Git)
tools/
  build.py           gera docs/ (somente biblioteca padrão do Python)
  serve.py           servidor local que imita o GitHub Pages
  optimize_images.py converte as originais em WebP (requer Pillow)
docs/                site gerado — é esta pasta que o GitHub Pages publica
```

## Como usar

```bash
python tools/build.py              # versão A em docs/, B em docs/v2/ e C em docs/v3/
python tools/build.py --theme b    # publica a B na raiz e as outras nas subpastas
python tools/serve.py              # abre em http://localhost:8080
python tools/build.py --env production            # versão final (A) para produção, sem /v2
python tools/build.py --env production --theme b  # versão final com a direção visual B (ou --theme c)
```

Depois de editar qualquer coisa em `src/`, rode o `build.py` e faça commit também da pasta `docs/`.

## Publicação no GitHub Pages

1. Em **Settings → Pages**: *Deploy from a branch*, branch `main`, pasta `/docs`.
2. O arquivo `docs/CNAME` já aponta para `magitronic.borzanti.com`.
3. No DNS do domínio `borzanti.com` (Squarespace): registro **CNAME** `magitronic` → `<seu-usuario>.github.io`.
4. Depois que o DNS propagar, marque **Enforce HTTPS** em Settings → Pages.

## Formulários

- Todos os formulários montam a mensagem com marca, modelo e defeito e abrem o WhatsApp da Magitronic.
- Com uma chave do [Web3Forms](https://web3forms.com) em `src/site.json` (`web3forms_key`), cada pedido também chega por e-mail. No formulário completo (`/orcamento`), quem escolhe “Ligação” ou “E-mail” recebe só o envio por e-mail.
- Cliques no WhatsApp e no telefone e o envio de formulários geram eventos no `dataLayer` (`whatsapp_click`, `phone_click`, `generate_lead`), prontos para o GTM (`gtm_id` em `site.json`).

## A confirmar com a Magitronic antes de publicar em produção

- [ ] Horário de funcionamento (hoje: seg–sex, 9h–18h, ilustrativo).
- [ ] Prazos médios de cada serviço e se querem mostrar preços “a partir de”.
- [ ] Coordenadas do endereço: as do site atual (`-23.6084, -46.6957`) parecem não bater com o endereço no mapa. O Google Maps também mostra o bairro como **Indianópolis**, não Moema. Alinhar com o Perfil da Empresa no Google.
- [ ] CNPJ e responsável pelos dados na política de privacidade.
- [ ] Fotos reais da loja e da bancada (as atuais são de banco de imagens).
- [ ] Escolher entre as versões A, B e C antes de publicar em produção.
- [ ] Os 7 artigos antigos do blog: migrar ou redirecionar.
- [ ] Redirecionamentos 301 das ~16.800 páginas geradas (`/assistencia-manutencao-notebook/...`) para os serviços. O GitHub Pages não faz 301; isso precisa ser feito na hospedagem de produção.
