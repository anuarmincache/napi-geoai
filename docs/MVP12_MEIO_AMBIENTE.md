# Meio Ambiente — consulta territorial sem indicador

Data da inspeção: 2026-11-18. Nenhum arquivo científico foi alterado e nenhum
download foi feito.

## O que está pronto

A malha municipal IBGE `municipio_2025` está validada: 399 feições, CRS
EPSG:4674, `validation_exportable` verdadeiro, área no atributo oficial
`AREA_KM2`. A página `app/pages/9_Meio_Ambiente.py` usa essa malha para busca,
mapa e comparação de área. A área não é indicador ambiental.

## O que não está no repositório

| Tema | Catálogo | Arquivo local | Validado |
|---|---|---|---|
| MapBiomas — uso e cobertura | `mapbiomas.brazil.lulc` | não | não |
| Unidades de conservação MMA/ICMBio/IAT | não | não | não |
| Recursos hídricos ANA/IAT | não | não | não |

## Próxima aquisição, ainda não autorizada

A tabela escolhida é a estatística municipal da Coleção 11, descrita em
`docs/MAPBIOMAS_COLECAO11.md`. O arquivo não foi baixado. O contrato em
`geoai/landcover/mapbiomas_col11.py` recusa a carga de produção enquanto
`LOCAL_FILE` e `CONTENT_SHA256` estiverem vazios.

1. Obter a tabela municipal oficial de uso do solo, não o raster nacional.
2. Conferir os códigos contra os 399 `CD_MUN` já validados. Código ausente ou
   divergente interrompe a carga.
3. Guardar coleção, ano, legenda de classes, resolução, licença e SHA-256 em
   proveniência, no mesmo padrão da malha.
4. Só então calcular área de classe e percentual. O denominador é a soma das
   classes folha em hectares. A diferença para `AREA_KM2` é declarada e não
   reescala a tabela.
5. Unidades de conservação e hidrografia seguem o mesmo critério: arquivo
   oficial, CRS, interseção espacial conferida e fail-closed. Nome de
   município declarado não substitui a geometria.

NDVI, Sentinel-2 e downloads públicos permanecem fora desta etapa.
