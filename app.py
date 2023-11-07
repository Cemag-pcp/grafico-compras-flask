from flask import Flask, render_template,request, redirect, url_for

import plotly.graph_objs as go

import pandas as pd
import numpy as np

import datetime
from datetime import datetime

import gspread

import cachetools

app = Flask(__name__)
cache_google_sheets = cachetools.LRUCache(maxsize=128)
cache_graficos = cachetools.LRUCache(maxsize=128)
cache_grupos = cachetools.LRUCache(maxsize=128)

@cachetools.cached(cache_google_sheets)
def tratamento():

    """
    Função para tratar as bases vinda do google sheets
    """

    hoje = datetime.now()
    data_string = hoje.strftime('%Y-%m-%d')

    dfSimulacao, dfDatas, dfPedidos = load_sheets()

    dfPedidos = dfPedidos[dfPedidos['Data Entrega'] != '']
    dfPedidos['Data Entrega'] = pd.to_datetime(dfPedidos['Data Entrega'], format='%d/%m/%Y')
    dfPedidos['Data Entrega'] = dfPedidos['Data Entrega'].apply(lambda x: hoje if x < hoje else x)
    dfPedidos['Data Entrega'] = dfPedidos['Data Entrega'].dt.strftime('%d/%m/%Y')

    dfDatasDiasUteis = dfDatas[dfDatas['natureza_tb1'] == 'saida'][['datas_tb1']]
    dfSimulacao = dfSimulacao[dfSimulacao['Média 3M'] != ''].iloc[:dfSimulacao.shape[0]-1]

    dfSimulacao['produto'] = dfSimulacao['Código'] + ' - ' + dfSimulacao['Descrição']

    qtdProdutosUnico = len(dfSimulacao['produto'].unique())

    tabelaGeralDataProduto = pd.merge(dfDatasDiasUteis.assign(key=1), dfSimulacao[['produto']].assign(key=1), on='key').drop('key', axis=1)
    tabelaGeralDataProduto['datas_tb1'] = pd.to_datetime(tabelaGeralDataProduto['datas_tb1'], format='%d/%m/%Y')
    tabelaGeralDataProduto = tabelaGeralDataProduto.sort_values(by='datas_tb1')
    tabelaGeralDataProduto['natureza'] = 'saida'

    # dezDiasUteis = tabelaGeralDataProduto['datas_tb1'].drop_duplicates().reset_index(drop=True)
    # dezDiasUteis = dezDiasUteis.loc[0:9].tolist()

    dfSimulacao = dfSimulacao.rename(columns={'Prev Con Mov Est(CMM)':'Prev', 'SIMULAÇÃO / (F.Pend/Fat.MM)':'Simulacao'})

    dfProdutos = dfSimulacao[['produto', 'Média 3M', 'Estoque Total', 'DEE - Dias Em Est.', 'Prev', 'Simulacao']]

    dfProdutos['Média 3M'] = dfProdutos['Média 3M'].apply(lambda x: float(x.replace(".", '').replace(',','.')))
    dfProdutos['Estoque Total'] = dfProdutos['Estoque Total'].apply(lambda x: float(x.replace(".", '').replace(',','.')))
    dfProdutos['DEE - Dias Em Est.'] = dfProdutos['DEE - Dias Em Est.'].apply(lambda x: float(x.replace(".", '').replace(',','.')))
    dfProdutos['Prev'] = dfProdutos['Prev'].apply(lambda x: float(x.replace(".", '').replace(',','.')))
    dfProdutos['Simulacao'] = dfProdutos['Simulacao'].apply(lambda x: float(x.replace(".", '').replace(',','.')))

    dfProdutos['maior_valor'] = dfProdutos[['Prev', 'Simulacao']].apply(max, axis=1)

    dfProdutos['consumoDiario'] = dfProdutos['maior_valor'] * 3 / 60
    dfProdutos['estoqueMinimo'] = dfProdutos['consumoDiario'] * 10

    tabelaProdutoGrupo = pd.read_csv("grupo.csv", sep=';')

    dfProdutos = dfProdutos.merge(tabelaProdutoGrupo, on='produto', how='left')

    # dfProdutos[dfProdutos['produto'].str.contains('116626')]

    dfPedidos = dfPedidos.rename(columns={'Recurso':'produto', 'Data Entrega':'datas_tb1'})
    dfPedidos['natureza'] = 'entrada'
    dfPedidos = dfPedidos[['produto', 'datas_tb1','natureza', 'Qde Ped']]
    dfPedidos = dfPedidos.iloc[:,1:5]
    dfPedidos['datas_tb1'] = pd.to_datetime(dfPedidos['datas_tb1'], format='%d/%m/%Y' )
    dfPedidos = dfPedidos[['datas_tb1', 'produto', 'natureza', 'Qde Ped']]

    #tabelaGeralDataProduto = tabelaGeralDataProduto.append(dfPedidos).sort_values(by='datas_tb1')

    tabelaGeralDataProduto = pd.concat([tabelaGeralDataProduto, dfPedidos]).sort_values(by='datas_tb1')
    tabelaGeralDataProduto = tabelaGeralDataProduto[tabelaGeralDataProduto['datas_tb1'] >= data_string].reset_index(drop=True)
    tabelaGeralDataProduto['Qde Ped'] = tabelaGeralDataProduto['Qde Ped'].astype(str)
    tabelaGeralDataProduto['Qde Ped'] = tabelaGeralDataProduto['Qde Ped'].apply(lambda x: float(x.replace(".","").replace(",",".")))
    tabelaGeralDataProduto = tabelaGeralDataProduto.replace(np.nan,0)
    tabelaGeralDataProduto = tabelaGeralDataProduto.rename(columns={'Qde Ped':'entradas'})

    qtdProdutosUnico = len(tabelaGeralDataProduto['produto'].unique())
    
    tabelaFinal = pd.DataFrame()
   
    # média dos primeiros dez dias úteis

    # dfDezDias = tabelaFinal[tabelaFinal['datas_tb1'].isin(dezDiasUteis)]    
    # dfDezDias['consumoDiario'] *= 10
    
    # tabelaFinal.loc[tabelaFinal["datas_tb1"].isin(dezDiasUteis), "consumoDiario"] = dfDezDias["consumoDiario"]

    # dfDezDias = pd.read_csv("dezdias.csv", sep=';', encoding='iso-8859-1')
    # dfDezDias = pd.read_csv("dezdiassimulado.csv", sep=';', encoding='iso-8859-1')
    # colunas = ['Recurso','Quantidade#Saída']
    # dfDezDias = dfDezDias.set_axis(colunas,axis=1,copy=False)

    # dfDezDias = dfDezDias.replace('"',"", regex=True)
    # dfDezDias = dfDezDias.replace('=',"", regex=True)

    # dfDezDias['Quantidade#Saída'] = dfDezDias['Quantidade#Saída'].replace('\.','', regex=True)
    # dfDezDias['Quantidade#Saída'] = dfDezDias['Quantidade#Saída'].replace(',','.', regex=True)
    # # dfDezDias['Quantidade#Saída'] = dfDezDias['Quantidade#Saída'].astype(float) * -1

    # dfDezDias = dfDezDias.rename(columns={'Recurso':'produto'})

    # Convertendo o array para uma Series do Pandas
    # series = pd.Series(produtosUnicos)

    # # Aplicando a pesquisa usando str.contains()
    # series[series.str.contains('262728')]

    for i in range(qtdProdutosUnico):
        
        try:

            produtosUnicos = tabelaGeralDataProduto['produto'].unique()

            # tabelaGeralDataProduto[tabelaGeralDataProduto['produto'].str.contains("COMP")].unique()

            produto = produtosUnicos[i]
            tabelaFiltrada = tabelaGeralDataProduto[tabelaGeralDataProduto['produto'] == produto].reset_index(drop=True)
            tabelaFiltrada.reset_index(drop=True, inplace=True) 
            tabelaFiltrada['saldoAtual'] = ''
            
            try:
                saldoAtual = dfProdutos[dfProdutos['produto'] == produto].reset_index(drop=True)['Estoque Total'][0]       
            except:
                continue
                        
            tabelaFiltrada = tabelaFiltrada.sort_values(by=['natureza'], ascending=False)
            tabelaFiltrada = tabelaFiltrada.sort_values(by=['datas_tb1'], ascending=True)
            
            tabelaFiltrada = tabelaFiltrada.reset_index(drop=True)

            tabelaFiltrada['saldoAtual'][0] = saldoAtual

            for j in range(1, len(tabelaFiltrada)):
            
                consumoDiario = dfProdutos[dfProdutos['produto'] == tabelaFiltrada['produto'][j]]['consumoDiario'].reset_index(drop=True)[0]
                
                # consumoDiario = dfProdutos[dfProdutos['produto'] == tabelaFiltrada['produto'][j]]['consumoDiario'].reset_index(drop=True)[0]

                entrada = tabelaFiltrada['entradas'][j]
                saldoOntem = tabelaFiltrada['saldoAtual'][j-1]

                if tabelaFiltrada['natureza'][j] == 'entrada':
                    
                    tabelaFiltrada['saldoAtual'][j] = float(saldoOntem) + float(entrada)

                else:    

                    tabelaFiltrada['saldoAtual'][j] = float(saldoOntem) - float(consumoDiario)

            tabelaFinal = pd.concat([tabelaFinal, tabelaFiltrada])

        except:
            continue
        
    tabelaFinal.reset_index(drop=True, inplace=True)

    # dfProdutos = dfProdutos.merge(dfDezDias, on='produto', how='left')

    dfProdutos.fillna(0, inplace=True)

    tabelaFinal = tabelaFinal.merge(dfProdutos, on='produto')

    # tabelaFinal.rename(columns={'Quantidade#Saída':'mediaDezDias'}, inplace=True)
    # dfProdutos.rename(columns={'Quantidade#Saída':'mediaDezDias'}, inplace=True)
    
    # for i in range(len(tabelaFinal)):
    #     if tabelaFinal['datas_tb1'][i] in dezDiasUteis:
    #         tabelaFinal['consumoDiario'][i] = float(dfProdutos[dfProdutos['produto'] == tabelaFinal['produto'][i]]['mediaDezDias'].reset_index(drop=True)) / 10
    #     else:
    #         continue

    #tabelaFinal['estoqueMinimo'] = tabelaFinal['consumoDiario'] * 10
    
    corrigido = tabelaFinal.copy()
    corrigido = tabelaFinal.merge(corrigido)
    corrigido = corrigido[corrigido['natureza'] == 'saida'][['datas_tb1','produto', 'grupo']]

    compraMaxima = dfProdutos[['produto','Média 3M','Estoque Total','estoqueMinimo', 'consumoDiario', 'maior_valor']]
 
    corrigido['valorCorrigido'] = 0

    tbCorrigida = pd.DataFrame()

    for i in range(qtdProdutosUnico):
        
        try:
            dados = corrigido[corrigido['produto'] == dfProdutos['produto'][i]].reset_index(drop=True)
        except:
            dados = pd.DataFrame()

        if len(dados) != 0:

            # if dados['grupo'][0] != 'Chapas':

            maximo = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['maior_valor']].values.tolist()[0][0]

            saldoInicial = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['Estoque Total']].values.tolist()[0][0]

            estoqueMinimo = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['estoqueMinimo']].values.tolist()[0][0]

            # mediaDezDias = float(compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['mediaDezDias']].values.tolist()[0][0]) / 10

            consumoDiario = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['consumoDiario']].values.tolist()[0][0]

            dados['valorCorrigido'][0] = saldoInicial 

            tamanho = len(dados)

            j=1

            while j <= tamanho-1:
                
                if dados['valorCorrigido'][j-1] <= float(estoqueMinimo) and float(estoqueMinimo) > 0:
                    
                    data = dados['datas_tb1'][j-1]
                    produto = dados['produto'][j-1]
                    grupo = dados['grupo'][j-1]
                    valorCorrigido = maximo + dados['valorCorrigido'][j-1]
                    
                    df_inserir = pd.DataFrame({'datas_tb1':[data],
                                                'produto':[produto],
                                                    'grupo':[grupo],
                                                    'valorCorrigido':[valorCorrigido]
                                                    }, index=[j-1 + 0.5])
                    
                    dados.index = dados.index.astype('float64')

                    dados = pd.concat([dados.loc[:j-1], df_inserir, dados.loc[j:]]).reset_index(drop=True)

                    j = j + 1

                    tamanho = len(dados)

                else:
                        
                    dados['valorCorrigido'][j] = dados['valorCorrigido'][j-1] - consumoDiario

                    j = j + 1

                    tamanho = len(dados)
      
            # else:
                
            #     maximo = 10000

            #     saldoInicial = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['Estoque Total']].values.tolist()[0][0]

            #     estoqueMinimo = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['estoqueMinimo']].values.tolist()[0][0]

            #     # mediaDezDias = float(compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['mediaDezDias']].values.tolist()[0][0]) / 10

            #     consumoDiario = compraMaxima[compraMaxima['produto'] == compraMaxima['produto'][i]].reset_index(drop=True)[['consumoDiario']].values.tolist()[0][0]

            #     dados = dados.reset_index(drop=True) 

            #     dados['valorCorrigido'][0] = saldoInicial

            #     j = 1
            #     dimensao = dados.shape[0]

            #     while j <= dimensao-1:
                    
            #         if dados['valorCorrigido'][j-1] <= float(estoqueMinimo):
                        
            #             data = dados['datas_tb1'][j-1]
            #             produto = dados['produto'][j-1]
            #             grupo = dados['grupo'][j-1]
            #             valorCorrigido = maximo + dados['valorCorrigido'][j-1]
                        
            #             df_inserir = pd.DataFrame({'datas_tb1':[data],
            #                                         'produto':[produto],
            #                                             'grupo':[grupo],
            #                                             'valorCorrigido':[valorCorrigido]
            #                                             }, index=[j-1 + 0.5])
                        
            #             dados.index = dados.index.astype('float64')

            #             dados = pd.concat([dados.loc[:j-1], df_inserir, dados.loc[j:]]).reset_index(drop=True)
                        
            #             dimensao = dados.shape[0]

            #             j = j + 1

            #         else:
                            
            #             dados['valorCorrigido'][j] = dados['valorCorrigido'][j-1] - consumoDiario
                        
            #             dimensao = dados.shape[0]

            #             j = j + 1
                
            #tbCorrigida = tbCorrigida.append(dados)
            tbCorrigida = pd.concat([tbCorrigida, dados])

        else:
            continue
    
    # dfProdutos['mediaDezDias'] = dfProdutos['mediaDezDias'].astype(float) / 10

    tabelaFinal = tabelaFinal[tabelaFinal['datas_tb1'] < max(tbCorrigida['datas_tb1'])]

    return tbCorrigida, tabelaFinal, dfProdutos


@cachetools.cached(cache_google_sheets)
def load_sheets():

    """
    Função para carregar as bases do google sheets
    """

    filename = 'service_account.json'

    ## Conectando com google sheets e acessando testesGraficos

    sheet = 'Análise Previsão de Consumo (CMM / NTP ) DEE'
    worksheet = 'testesGraficos'

    sa = gspread.service_account(filename)
    sh = sa.open(sheet)
    wks = sh.worksheet(worksheet)

    cabecalho = wks.row_values(2)
    
    dfDatas = wks.get()
    dfDatas = pd.DataFrame(dfDatas)
    dfDatas = dfDatas.set_axis(cabecalho, axis=1, copy=False)
    dfDatas = dfDatas.iloc[2:]
        
    ## Conectando com google sheets e acessando Análise Previsão de Consumo (CMM / NTP ) DEE

    sheet = 'Análise Previsão de Consumo (CMM / NTP ) DEE'
    worksheet = 'Simulação Pend. Vendas'

    sa = gspread.service_account(filename)
    sh1 = sa.open(sheet)
    wks1 = sh1.worksheet(worksheet)
    dfSimulacao = wks1.get()
    dfSimulacao = pd.DataFrame(dfSimulacao)

    cabecalho = wks1.row_values(2)

    #tratando planilha Análise Previsão de Consumo (CMM / NTP ) DEE
    dfSimulacao = dfSimulacao.set_axis(cabecalho, axis=1, copy=False)
    dfSimulacao = dfSimulacao.iloc[2:]

    ## Conectando com google sheets e acessando Análise Previsão de Consumo (CMM / NTP ) DEE

    sheet = 'Análise Previsão de Consumo (CMM / NTP ) DEE'
    worksheet = 'Dados Pedidos'

    sa = gspread.service_account(filename)
    sh2 = sa.open(sheet)
    wks2 = sh2.worksheet(worksheet)
    dfPedidos = wks2.get()
    dfPedidos = pd.DataFrame(dfPedidos)
    dfPedidos = dfPedidos.iloc[:,:28]
    dfPedidos.dropna(axis=1, inplace=True)

    cabecalho = wks2.row_values(1)
    cabecalho = cabecalho[:28]
    #tratando planilha Análise Previsão de Consumo (CMM / NTP ) DEE
    dfPedidos = dfPedidos.set_axis(cabecalho, axis=1, copy=False)
    dfPedidos = dfPedidos.iloc[1:]

    ## Conectando com google sheets e acessando Análise Previsão de Consumo (CMM / NTP ) DEE

    # sheet = 'Análise Previsão de Consumo (CMM / NTP ) DEE'
    # worksheet = 'Dados Simulação'

    # sa = gspread.service_account(filename)
    # sh2 = sa.open(sheet)
    # wks2 = sh2.worksheet(worksheet)
    # planSimulacao = wks2.get()
    # planSimulacao = pd.DataFrame(planSimulacao)

    # planSimulacao.dropna(axis=1, inplace=True)

    # cabecalho = wks2.row_values(1)

    # #tratando planilha Análise Previsão de Consumo (CMM / NTP ) DEE
    # planSimulacao = planSimulacao.set_axis(cabecalho[0:23], axis=1)
    # planSimulacao = planSimulacao.iloc[1:]

    # planSimulacao['Código'] = planSimulacao['Código'] + " - " + planSimulacao['Descrição']

    return dfSimulacao, dfDatas, dfPedidos


@app.route("/resetar-cache", methods=['POST'])
def resetar_cache():

    """
    Função para limpar caches.
    """

    cache_google_sheets.clear()
    cache_graficos.clear()
    cache_grupos.clear()

    return redirect(url_for('plot'))


@cachetools.cached(cache_graficos)
def gerar_graficos_grupo(selectGrupo):

    """
    Função para gerar gráficos com base no grupo escolhido
    """

    print(selectGrupo)
    
    graficos = []
    tabelas = []

    # produto1='240471 - CILINDRO TELESCÓPICO CBH 6T 10 OC NV'

    tbCorrigida, tabelaFinal, dfProdutos = tratamento()

    # dfProdutos[dfProdutos['produto'] == produto1]
    # tbCorrigida[tbCorrigida['produto'] == produto1]
    # tabelaFinal[tabelaFinal['produto'] == produto1]

    tbCorrigida.dropna(inplace=True)
    tabelaFinal.dropna(inplace=True)
    dfProdutos.dropna(inplace=True)

    tbCorrigida = tbCorrigida[tbCorrigida['grupo'] == selectGrupo]
    tabelaFinal = tabelaFinal[tabelaFinal['grupo'] == selectGrupo]

    tabelaFinal = tabelaFinal.sort_values(['datas_tb1', 'natureza'], ascending=[True, False]).reset_index(drop=True)
    
    tabelaFinal['valor_0'] = 0
    
    produtosUnico = tbCorrigida['produto'].unique()

    for produto in range(len(produtosUnico)):
        
        df_grafico = tabelaFinal[tabelaFinal['produto'] == produtosUnico[produto]]
        df_grafico1 = tbCorrigida[tbCorrigida['produto'] == produtosUnico[produto]]
        
        # df_grafico[df_grafico['datas_tb1'] == '2023-05-30'][['datas_tb1','produto','natureza','entradas']]

        titulo = 'Produto: ' + produtosUnico[produto]

        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['saldoAtual'], mode='lines', name='Consumo real'))
        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['valor_0'], mode='lines', name='zero'))
        fig.add_trace(go.Scatter(x=df_grafico1['datas_tb1'], y=df_grafico1['valorCorrigido'], mode='lines', name='Consumo corrigido'))
        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['estoqueMinimo'], mode='lines', name='Estoque mínimo'))

        inicio = min(df_grafico['datas_tb1'])  # Defina a data de início com base nos rótulos originais
        fim = max(df_grafico['datas_tb1'])  # Defina a data de fim com base nos rótulos originais
        novos_rotulos = pd.date_range(start=inicio, end=fim, freq='5D')

        fig.update_layout(title={'text': titulo, 'x': 0.2}, xaxis_title='Data', xaxis_tickangle=45, yaxis_title='Valor', width=800, height=600, xaxis=dict(tickmode='array', tickvals=novos_rotulos, tickformat='%Y-%m-%d'))

        tabela = dfProdutos[dfProdutos['produto'] == produtosUnico[produto]].values.tolist()
        
        tabelas.append(tabela)
        graficos.append(fig.to_html())

        graficos_tabelas = list(zip(graficos,tabelas))

    return graficos_tabelas


@cachetools.cached(cache_grupos)
def grupos():

    """
    Função para carregar os grupos do arquivo "grupo.csv"
    """

    dfGrupo = pd.read_csv('grupo.csv', sep=';') 

    tbGrupo = dfGrupo[['grupo']]

    grupoUnico = tbGrupo['grupo'].unique()
    listaGrupos = ['Selecione']
    # listaProdutos = ['Selecione']

    for i in range(len(grupoUnico)):
        listaGrupos.append(grupoUnico[i])

    listaGrupos = [valor for valor in listaGrupos if valor and not isinstance(valor, float) and valor.strip()]

    return listaGrupos


@cachetools.cached(cache_graficos)
def gerar_graficos_produto(selectProduto):

    """
    Função para gerar gráficos com base no produto escolhido
    """

    graficos = []
    tabelas = []

    tbCorrigida, tabelaFinal, dfProdutos = tratamento()

    tbCorrigida.dropna(inplace=True)
    tabelaFinal.dropna(inplace=True)
    dfProdutos.dropna(inplace=True)

    tbCorrigida['produto'].unique()

    tbCorrigida = tbCorrigida[tbCorrigida['produto'] == selectProduto]
    tabelaFinal = tabelaFinal[tabelaFinal['produto'] == selectProduto]

    tabelaFinal = tabelaFinal.sort_values(['datas_tb1', 'natureza'], ascending=[True, False]).reset_index(drop=True)

    tabelaFinal['valor_0'] = 0

    produtosUnico = tbCorrigida['produto'].unique()

    for produto in range(len(produtosUnico)):
        
        df_grafico = tabelaFinal[tabelaFinal['produto'] == produtosUnico[produto]]
        df_grafico1 = tbCorrigida[tbCorrigida['produto'] == produtosUnico[produto]]

        titulo = 'Produto: ' + produtosUnico[produto]

        fig = go.Figure()

        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['saldoAtual'], mode='lines', name='Consumo real'))
        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['valor_0'], mode='lines', name='zero'))
        fig.add_trace(go.Scatter(x=df_grafico1['datas_tb1'], y=df_grafico1['valorCorrigido'], mode='lines', name='Consumo corrigido'))
        fig.add_trace(go.Scatter(x=df_grafico['datas_tb1'], y=df_grafico['estoqueMinimo'], mode='lines', name='Estoque mínimo'))

        inicio = min(df_grafico['datas_tb1'])  # Defina a data de início com base nos rótulos originais
        fim = max(df_grafico['datas_tb1'])  # Defina a data de fim com base nos rótulos originais
        novos_rotulos = pd.date_range(start=inicio, end=fim, freq='5D')

        fig.update_layout(title={'text': titulo, 'x': 0.2}, xaxis_title='Data', xaxis_tickangle=45, yaxis_title='Valor', width=800, height=600, xaxis=dict(tickmode='array', tickvals=novos_rotulos, tickformat='%Y-%m-%d'))

        tabela = dfProdutos[dfProdutos['produto'] == produtosUnico[produto]].values.tolist()
        
        tabelas.append(tabela)
        graficos.append(fig.to_html())

    graficos_tabelas = list(zip(graficos, tabelas))
    
    return graficos_tabelas


@app.route('/', methods=['POST','GET'])
def plot():

    """
    Rota para renderizar os gráficos gerados.
    """

    selectGrupo = request.form.get('grupo')
    selectProduto = request.form.get('produto')

    print(selectGrupo, selectProduto)

    if selectProduto != 'Selecione':

        graficos_tabelas = gerar_graficos_produto(selectProduto)
        nome_grupo = selectProduto

    elif selectGrupo != 'Selecione':

        graficos_tabelas = gerar_graficos_grupo(selectGrupo)
        nome_grupo = selectGrupo

    listaGrupos = grupos()

    tbCorrigida, tabelaFinal, dfProdutos = tratamento()
    tbCorrigida.dropna(inplace=True)
    listaProdutos = tbCorrigida['produto'].unique().tolist()
    listaProdutos.insert(0, 'Selecione')
    
    return render_template("index.html", graficos_tabelas=graficos_tabelas, listaGrupos=listaGrupos,
                            listaProdutos=listaProdutos, nome_grupo=nome_grupo)


if __name__ == '__main__':
    app.run(debug=True)