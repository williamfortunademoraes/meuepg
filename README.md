# Meu EPG

XMLTV para os canais Tvvio, gerado a partir do XMLTV brasileiro.

- URL para o Nuvio + IPTV: https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- Fonte XMLTV: https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/br.xml.gz
- `pareamentos.csv` registra o mapeamento revisado dos IDs Tvvio para os canais da fonte.
- `build_epg.py` reconstrói o XMLTV sem dependências externas além da biblioteca padrão do Python.
- GitHub Actions atualiza `epg.xml` e `pareamentos.csv` a cada seis horas e também pode ser iniciado manualmente na aba Actions.

A grade só pode ser gerada para canais com correspondência na fonte. Feeds de evento sem grade fixa e canais sem correspondência ficam fora do XMLTV.
