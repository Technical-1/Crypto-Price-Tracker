import time
import requests
import os
import json
import sys

r1 = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin%2Cethereum%2C1inch%2Cmirror-protocol%2Cthe-graph%2Cdecentraland%2Cenjincoin%2Cmaker%2Crepublic-protocol%2Cbarnbridge%2Corigin-protocol%2Cclover-finance%2Cstellar%2Cuniswap%2Ceos&vs_currencies=usd&include_24hr_change=true')

originalHoldings = {"ethereum":          {"total":1,"cost":200},
                    "bitcoin":           {"total":1,"cost":200},
                    "1inch":             {"total":1,"cost":20},
                    "mirror-protocol":   {"total":1,"cost":20},
                    "the-graph":         {"total":1,"cost":20},
                    "decentraland":      {"total":1,"cost":20},
                    "enjincoin":         {"total":1,"cost":20},
                    "maker":             {"total":1,"cost":20},
                    "republic-protocol": {"total":1,"cost":20},
                    "barnbridge":        {"total":1,"cost":20},
                    "origin-protocol":   {"total":1,"cost":20},
                    "clover-finance":    {"total":1,"cost":20},
                    "stellar":           {"total":1,"cost":20},
                    "uniswap":           {"total":1,"cost":20},
                    "eos":               {"total":1,"cost":20}}

priceData = json.loads(r1.text)

print("        Coin              Profit      Cost     24hr %")
print("---------------------   ----------   ------   ---------")

for key, value in originalHoldings.items():
    avgCost = value['cost']/value['total']
    profitPerCoin = priceData[key]['usd']-avgCost
    profit = profitPerCoin*value['total']

    print("%20s     %8.2f     %4d      %5.2f" % (key, profit, value['cost'],priceData[key]['usd_24h_change']))
