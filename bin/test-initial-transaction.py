#!/usr/bin/env python3

import argparse
import json
from pprint import pprint
import random
from urllib.error import HTTPError, URLError
import urllib.request

from clove.network import BitcoinTestNet
from clove.network.bitcoin import Utxo
from clove.utils.bitcoin import satoshi_to_btc

ALICE_ADDRESS = 'msJ2ucZ2NDhpVzsiNE5mGUFzqFDggjBVTM'
BOB_ADDRESS = 'mmJtKA92Mxqfi3XdyGReza69GjhkwAcBN1'
ALICE_PK = 'cSYq9JswNm79GUdyz6TiNKajRTiJEKgv4RxSWGthP3SmUHiX9WKe'


def get_utxo(address, amount):
    print('>>> Searching for UTXO\'s')
    api_url = \
        f'https://api.blockcypher.com/v1/btc/test3/addrs/{address}/full?limit=50?unspentOnly=true&includeScript=true'
    utxo = []
    total = 0
    try:
        with urllib.request.urlopen(api_url) as url:
            if url.status != 200:
                return
            data = json.loads(url.read().decode())
            # try to use different transactions each time
            random.shuffle(data['txs'])
            for txs in data['txs']:
                for i, output in enumerate(txs['outputs']):
                    if not output['addresses'] or output['addresses'][0] != address \
                            or output['script_type'] != 'pay-to-pubkey-hash' or 'spent_by' in output:
                        continue
                    value = satoshi_to_btc(output['value'])
                    utxo.append(
                        Utxo(
                            tx_id=txs['hash'],
                            vout=i,
                            value=value,
                            tx_script=output['script'],
                        )
                    )
                    total += value
                    if total > amount:
                        return utxo
            exit(f'>>> Cannot find enough UTXO\'s. {total:.8f} is all that you\'ve got.')
    except (URLError, HTTPError):
        print('>>> Cannot get UTXO\'s from API')
        return


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Generate and publish atomic swap initial transaction.")
    parser.add_argument('-s', '--sender', help='Sender address', type=str, default=ALICE_ADDRESS)
    parser.add_argument('-r', '--recipient', help='Recipient address', type=str, default=BOB_ADDRESS)
    parser.add_argument('-a', '--amount', help='Transaction amount', type=float)
    parser.add_argument('-p', '--private-key', help='Private key', type=str, default=ALICE_PK)

    args = parser.parse_args()
    if not args.amount:
        args.amount = float(input('How many BTC do you want to transfer? ').replace(',', '.'))

    btc_network = BitcoinTestNet()

    print('>>> Creating transaction for BitcoinTestNet')
    print('>>> Sender address:\t', args.sender)
    print('>>> Recipient address:\t', args.recipient)
    print('>>> Transaction amount:\t', args.amount)

    wallet = btc_network.get_wallet(private_key=args.private_key)
    utxo = get_utxo(args.sender, args.amount)

    print(f'>>> Found {len(utxo)} UTXO\'s')
    pprint(utxo)
    transaction = btc_network.atomic_swap(args.sender, args.recipient, args.amount, utxo)

    print('>>> Adding fee and signing')
    transaction.add_fee_and_sign(wallet)

    print('>>> Transaction ready to be published')
    details = transaction.show_details()
    pprint(details)

    publish = input('Do you want to publish this transaction (y/n): ')
    if publish != 'y':
        print('>>> Bye!')
        exit()

    print('>>> Publishing transaction')
    transaction.publish()

    print('>>> Transaction published!')
    print(f'>>> https://live.blockcypher.com/btc-testnet/tx/{details["transaction_hash"]}/')