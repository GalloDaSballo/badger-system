from assistant.subgraph.config import subgraph_config
from rich.console import Console
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from decimal import *
getcontext().prec = 20
console = Console()

url = subgraph_config["url"]
transport = AIOHTTPTransport(url=url)
client = Client(transport=transport, fetch_schema_from_transport=True)


def fetch_all_geyser_events(geyserId):
    print("fetch_geyser_events", geyserId)
    # Get all geysers
    query = """
    {
    geysers {
        id
        totalStaked
        stakeEvents(orderBy: blockNumber) {
        id, geyser {
            id
        }, user, amount, total, timestamp, blockNumber, data
            }
        unstakeEvents(orderBy: blockNumber) {
        id, geyser {
            id
        }, user, amount, total, timestamp, blockNumber, data
            }
    }
    }
    """

    variables = {"geyserId": geyserId}
    endpoint = HTTPEndpoint(url, headers)
    result = endpoint(query)

    unstakes = []
    stakes = []
    totalStaked = 0

    # Find this geyser
    for entry in result["data"]["geysers"]:
        if entry["id"] == geyserId:
            stakes = entry["stakeEvents"]
            unstakes = entry["unstakeEvents"]
            totalStaked = entry["totalStaked"]

    # console.log(result['data'])
    return {
        "id": geyserId,
        "unstakes": unstakes,
        "stakes": stakes,
        "totalStaked": totalStaked,
    }


def fetch_sett_balances(settId, startBlock):
    console.print(
        "[bold green] Fetching sett balances {}[/bold green]".format(settId)
    )
    query = gql(
        """
        query balances_and_events($vaultID: Vault_filter, $blockHeight: Block_height) {
            vaults(block: $blockHeight, where: $vaultID) {
                balances(orderBy: netDeposits, orderDirection: desc) {
                    id
                    account {
                        id
                    }
                    shareBalanceRaw
                  }
                }
            }
        """
    )
    variables = {"blockHeight": {"number": startBlock}, "vaultID": {"id": settId}}
    results = client.execute(query, variable_values=variables)
    if len(results["vaults"]) == 0:
        return {}

    balances = {}
    for result in results["vaults"][0]["balances"]:
        account = result["id"].split("-")[0]
        balances[account] = int(result["shareBalanceRaw"])
    return balances


def fetch_geyser_events(geyserId, startBlock):
    console.print(
        "[bold green] Fetching Geyser Events {}[/bold green]".format(geyserId)
    )

    query = gql(
        """query($geyserID: Geyser_filter,$blockHeight: Block_height)
    {
      geysers(where: $geyserID,block: $blockHeight) {
          id
          totalStaked
          stakeEvents(first:1000) {
              id
              user,
              amount
              timestamp,
              total
          }
          unstakeEvents(first:1000) {
              id
              user,
              amount
              timestamp,
              total
          }
      }
    }
    """
    )
    variables = {"geyserID": {"id": geyserId}, "blockHeight": {"number": startBlock}}
    result = client.execute(query, variable_values=variables)
    if len(result["geysers"]) == 0:
        stakes = []
        unstakes = []
        totalStaked = 0
    else:
        stakes = result["geysers"][0]["stakeEvents"]
        unstakes = result["geysers"][0]["unstakeEvents"]
        totalStaked = result["geysers"][0]["totalStaked"]

    console.log("Processing {} stakes".format(len(stakes)))
    console.log("Processing {} unstakes".format(len(unstakes)))
    return {
        "stakes": stakes,
        "unstakes": unstakes,
        "totalStaked": totalStaked
    }


def fetch_sett_transfers(settID, startBlock, endBlock):
    console.print(
        "[bold green] Fetching Sett Deposits/Withdrawals {}[/bold green]".format(settID)
    )
    query = gql(
        """
        query sett_transfers($vaultID: Vault_filter, $blockHeight: Block_height) {
            vaults(block: $blockHeight, where: $vaultID) {
                deposits(first:1000) {
                    pricePerFullShare
                    account {
                     id
                    }
                    amount
                    transaction {
                        timestamp
                        blockNumber
                    }
                }
                withdrawals(first:1000) {
                    pricePerFullShare
                    account {
                     id
                    }
                    amount
                    transaction {
                        timestamp
                        blockNumber
                    }
                }
            }
        }
    """
    )
    variables = {"vaultID": {"id": settID}, "blockHeight": {"number": endBlock}}

    results = client.execute(query, variable_values=variables)

    def filter_by_startBlock(transfer):
        return int(transfer["transaction"]["blockNumber"]) > startBlock

    def convert_amount(transfer):
        ppfs = Decimal(transfer["pricePerFullShare"]) / Decimal(1e18)
        transfer["amount"] = round(Decimal(transfer["amount"]) / Decimal(ppfs))
        return transfer

    def negate_withdrawals(withdrawal):
        withdrawal["amount"] = -withdrawal["amount"]
        return withdrawal


    deposits = map(convert_amount, results["vaults"][0]["deposits"])
    withdrawals = map(
        negate_withdrawals,
        map(convert_amount, results["vaults"][0]["withdrawals"]),
    )

    deposits = list(filter(filter_by_startBlock, list(deposits)))
    withdrawals = list(filter(filter_by_startBlock, list(withdrawals)))
    console.log("Processing {} deposits".format(len(deposits)))
    console.log("Processing {} withdrawals".format(len((withdrawals))))

    return sorted(
        [*deposits, *withdrawals],
        key=lambda t: t["transaction"]["timestamp"],
    )

def fetch_harvest_farm_events():
    query = gql("""
        query fetch_harvest_events {
            farmHarvestEvents(first:1000,orderBy: blockNumber,orderDirection:asc) {
                id
                farmToRewards
                blockNumber
                totalFarmHarvested
                timestamp
            }
        }

    """)
    results = client.execute(query)
    return results["farmHarvestEvents"]
