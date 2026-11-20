# Meu EPG

XMLTV unificado para os canais Tvvio, gerado periodicamente a partir de fontes XMLTV brasileiras.

- URL do EPG: https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- Fontes BrazilTVEPG, rootcoder/epgtv (inclui mapeamento regional RJ), EPG-Scrapper-BR e epg.pw Brasil.
- `pareamentos.csv` lista os canais e o estado do mapeamento.
- `cobertura.csv` informa quantos programas foram gerados por canal e qual fonte contribuiu.
- GitHub Actions atualiza os arquivos a cada seis horas e aceita execução manual.

Fontes indisponíveis são ignoradas. Programas duplicados são removidos por canal, início e título; a ordem da lista de fontes define a prioridade. Canais sem correspondência ou feeds sem grade fixa permanecem no relatório.
