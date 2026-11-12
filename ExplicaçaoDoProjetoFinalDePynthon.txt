O projeto foi feito em etapas, usando **Pandas** para tratar e analisar os dados e **Matplotlib** para criar os gráficos e o PDF.

1. **Leitura da base:** o script `analise_vendas.py` abre `vendas.csv`, que tem 50 mil registros, 15 colunas, separador `;` e codificação UTF-8. Ele confere se as colunas necessárias estão presentes e converte datas e valores numéricos para os tipos adequados.

2. **Limpeza:** remove 150 linhas duplicadas e padroniza grafias de categorias, status e formas de pagamento. As cidades ausentes são marcadas como “Não informado”. Datas inválidas são excluídas das análises por período; quantidades inválidas e descontos fora do intervalo permitido são excluídos dos indicadores financeiros, sem tentar adivinhar valores.

3. **Cálculos:** considera apenas vendas concluídas como receita reconhecida. Calcula o valor bruto por preço unitário vezes quantidade e o líquido subtraindo o desconto. Para contagem de transações, usa o identificador único do pedido — não conta cada item como um pedido.

4. **Análises e gráficos:** calcula faturamento por categoria, período, vendedor, forma de pagamento e estado; também identifica produtos mais vendidos e compara região, categoria e ano. A partir desses resultados, gera oito gráficos e uma recomendação estratégica, explicitando as limitações dos dados.

5. **Entrega:** o script grava o relatório interpretativo em Markdown, as imagens em `resultado\graficos` e o documento em PDF em `resultado\relatorio_analise_vendas.pdf`.