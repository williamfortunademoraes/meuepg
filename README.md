# Meu EPG

XMLTV unificado para os canais Tvvio, gerado periodicamente a partir das fontes XMLTV do BrazilTVEPG.

- URL do EPG: https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- Fontes combinadas com prioridade: globo.xml, maissbt.xml, vivoplay.xml, xsports.xml, epg.xml e claro.xml.
- `pareamentos.csv` lista os canais e o estado do mapeamento.
- `cobertura.csv` informa quantos programas foram gerados por canal e qual fonte contribuiu.
- GitHub Actions atualiza os arquivos a cada seis horas e aceita execução manual na aba Actions.

Programas duplicados são removidos por canal, horário de início e título. Canais sem correspondência ou feeds sem grade fixa permanecem indicados no relatório.
