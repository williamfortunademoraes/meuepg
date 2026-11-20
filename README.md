# Meu EPG

XMLTV unificado para os canais Tvvio, gerado periodicamente a partir de fontes XMLTV brasileiras.

- **URL do EPG:** https://raw.githubusercontent.com/williamfortunademoraes/meuepg/main/epg.xml
- **Atualização:** automática a cada 6 horas pelo GitHub Actions; também aceita execução manual.
- **Janela da programação:** programas que intersectam o período móvel de 6 horas anteriores até 48 horas à frente. Um programa que já está no ar pode ter começado antes da janela; um programa em andamento no fim pode terminar depois dela.
- **Cobertura da última geração:** 105 canais com programação; 28 feeds de evento sem grade fixa; 22 canais sem correspondência de EPG. Consulte [`cobertura.csv`](cobertura.csv) para os dados atualizados por canal.

## Fontes e critérios

Fontes BrazilTVEPG, rootcoder/epgtv (inclui mapeamento regional RJ), EPG-Scrapper-BR, epg.pw Brasil, grade oficial do AMC Séries e EPG-BR de vinnyoliveira (fallback restrito a MTV e Comedy Central). O arquivo `epg-rich.xml.gz` da mesma fonte só complementa metadados quando canal, título e horário (diferença máxima de 5 minutos) coincidem; ele não muda os horários nem os títulos publicados.

Programas duplicados são removidos por canal, início e título. Quando fontes apresentam horários sobrepostos, prevalece a primeira fonte na ordem de prioridade; outras fontes só preenchem intervalos livres. Blocos genéricos cujo título apenas repete o nome do canal são descartados. Assim, o XML mantém no máximo um programa por canal em cada intervalo.

`pareamentos.csv` lista os IDs de origem e o estado do mapeamento. `cobertura.csv` informa quantos programas foram gerados por canal e qual fonte contribuiu.

## Canais com programação

A lista abaixo reflete a última geração do EPG:

<details>
<summary>105 canais</summary>

A&E, AMC, AMC Séries, AXN, Cinemax, Globoplay Novelas, HBO, HBO 2, HBO Family, HBO Mundi, HBO Plus, HBO Pop, HBO Signature, HBO Xtreme, Megapix, Sony Channel, Space, Studio Universal, Telecine Action, Telecine Cult, Telecine Fun, Telecine Pipoca, Telecine Premium, Telecine Touch, TNT Novelas, TNT Series, Universal TV, USA, Warner Channel, Adult Swim, Animal Planet, Comedy Central, Discovery Channel, Discovery Home & Health, Discovery Science, Discovery Theater, Discovery Turbo, Discovery World, Food Network, GNT, HGTV, History, History 2, Investigation Discovery, MTV, Multishow, BandNews, CNN Brasil, GloboNews, Jovem Pan News, Record News, Band Sports, Canal Off, Combate, Disney+, ESPN, ESPN 2, ESPN 3, ESPN 4, ESPN 5, ESPN 6, GE TV, N Sports, Nosso Futebol, Paramount +, Premiere 2, Premiere 3, Premiere 4, Premiere 5, Premiere 6, Premiere 7, Premiere Clubes, SporTV, SporTV 2, SporTV 3, SportyNet, SportyNet +1, SportyNet +2, SportyNet +3, TNT, Xsports, Globo Rio, Globo São Paulo, Record Rio, Record São Paulo, RedeTV!, SBT Rio, SBT São Paulo, TV Cultura, Cartoon Network, Cartoonito, Discovery Kids, DreamWorks, Gloob, Gloobinho, Nick Jr., Tooncast, TV Ra Tim Bum, Canção Nova, Novo Tempo, Pai Eterno, Rede Gospel, Rede Vida, TV Aparecida, TV Evangelizar

</details>
