# Meu EPG

XMLTV para os canais Tvvio, gerado periodicamente a partir da fonte XMLTV Brasil.

- URL para o Nuvio + IPTV: https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- Fonte atualizada: https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/claro.xml
- `pareamentos.csv` mostra as correspondências recalculadas a cada execução.
- `build_epg.py` gera o XMLTV usando apenas a biblioteca padrão do Python.
- GitHub Actions roda a cada seis horas e também aceita execução manual na aba Actions.

Canais sem correspondência na fonte ou feeds de evento sem grade fixa não recebem programação.
