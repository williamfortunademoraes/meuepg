# Meu EPG

XMLTV unificado para os canais Tvvio, gerado periodicamente a partir de fontes XMLTV brasileiras.

- URL do EPG: https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- Fontes: BrazilTVEPG (globo, +SBT, Vivo Play, Xsports, epg.xml e Claro), EPG-Scrapper-BR e epg.pw Brasil.
- `pareamentos.csv` lista os canais e o estado do mapeamento.
- `cobertura.csv` informa quantos programas foram gerados por canal e qual fonte contribuiu.
- GitHub Actions atualiza os arquivos a cada seis horas e aceita execução manual na aba Actions.

As fontes suplementares são ignoradas se estiverem indisponíveis. Programas duplicados são removidos por canal, início e título; as fontes aparecem em ordem de prioridade. Canais sem correspondência ou feeds sem grade fixa continuam indicados no relatório.
