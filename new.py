import datetime
import enum
import json
import logging
from collections import namedtuple
from time import ctime
from urllib.parse import urlencode

import pandas as pd
import requests
from requests.utils import requote_uri

logger = logging.getLogger(__name__)

Instrument = namedtuple('Instrument', ['exchange', 'token', 'symbol',
                                       'name', 'expiry', 'lot_size'])


class Requests(enum.Enum):
    PUT = 1
    DELETE = 2
    GET = 3
    POST = 4


class TransactionType(enum.Enum):
    Buy = 'B'
    Sell = 'S'


class OrderType(enum.Enum):
    Market = 'MKT'
    Limit = 'LMT'
    StopLoss = 'SL'
    StopLossMarket = 'SL-M'


class InstrumentType(enum.Enum):
    Index_Option = 'OPTIDX'
    Index_Future = 'FUTIDX'
    Equity = 'EQUITY'
    Stock_Option = 'OPTSTK'
    Stock_Future = 'FUTSTK'
    Currency_Future = 'FUTCUR'
    Currency_Option = 'OPTCUR'
    Commodity_Future = 'FUTCOM'
    Commodity_Option = 'OPTCOM'


class ProductType(enum.Enum):
    Intraday = 'I'
    Margin = 'M'
    Delivery = 'C'
    CoverOrder = 'V'
    BracketOrder = 'B'  # productlist


def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i


class Shoonya:
    # dictionary object to hold settings
    __service_config = {
        'headers': {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
        'host': 'https://shoonya.finvasia.com',
        'routes': {
            'jwt_token': '/jwt/token',  # Done
            'login': '/trade/login',  # Done
            'holdings': '/trade/getHoldings',  # Done
            'limits': '/trade/getLimits',  # Done
            'detailed_limits': '/trade/getLimitsMainData',  # Done
            'positions': '/trade/getNetposition',  # Done
            'place_order': '/trade/placeorder',
            'place_cover_order': '/trade/coverOrder',
            'place_bracket_order': '/trade/bracketorder',
            'get_orders': '/trade/getOrderbook',  # Done
            'get_order_info': '/trade/orderDetails',  # Done
            'modify_order': '/trade/modifyOrder',  # Done
            'cancel_order': '/trade/cancelorder',  # Done
            'trade_book': '/trade/getTradebook',  # Done
        },
    }

    def __init__(self, username, access_token, panno, key, token, usercode, usertype,
                 master_contracts_to_download):
        """ logs in and gets enabled exchanges and products for user """
        self.__access_token = access_token
        self.__username = username
        self.__panno = panno
        self.__keyid = key
        self.__tokenid = token
        self.__usertype = usertype
        self.__usercode = usercode
        self.__master_contracts_by_token = {}
        self.__master_contracts_by_symbol = {}
        for e in master_contracts_to_download:
            self.__get_master_contract(e)

    @staticmethod
    def login_and_get_authorizations(username, password, panno):
        s = requests.session()
        config = Shoonya.__service_config
        headers = config['headers']
        client_data = {"userName": username, "pan": panno,
                       "role": "admin", "pass": password}
        params = str(client_data).replace(" ", "")
        url = f"{config['host']}{config['routes']['jwt_token']}"
        requests.urllib3.disable_warnings
        res = s.post(url, data=params, headers=headers)
        token = res.text
        headers['Authorisation'] = "Token " + token
        url = f"{config['host']}{config['routes']['login']}"
        res = s.post(url, data=params, headers=headers)
        key = res.json()['key']
        token_id = res.json()['userdata']['TOKENID']
        usercode = res.json()['userdata']['USERID']
        usertype = res.json()['userdata']['UM_USER_TYPE']
        panno = res.json()['userdata']['PANNO']
        key = key.replace("=", "%3D")
        return {
            'access_token': "Token " + token,
            'key': key,
            'token_id': token_id,
            'user_id': username,
            'usercode': usercode,
            'usertype': usertype,
            'panno': panno,
        }

    def get_limits(self):
        """ Get balance/margins """
        data = {"token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('limits', Requests.POST, None, data)

    def __get_master_contract(self, exchange):
        """ returns all the tradable contracts of an exchange
            placed in an OrderedDict and the key is the token
        """
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Accept': 'application/json'}
        url = f'https://ant.aliceblueonline.com/api/v2/contracts.json?exchanges={exchange}'
        body = requests.get(url, headers=headers).json()
        master_contract_by_token = {}
        master_contract_by_symbol = {}
        for sub in body:
            for scrip in body[sub]:
                # convert token
                token = int(scrip['code'])

                # convert symbol to upper
                symbol = scrip['symbol']

                # convert expiry to none if it's non-existent
                if ('expiry' in scrip):
                    expiry = datetime.datetime.fromtimestamp(
                        scrip['expiry']).date()
                else:
                    expiry = None

                # convert lot size to int
                lot_size = scrip['lotSize'] if ('lotSize' in scrip) else None
                # Name & Exchange
                name = scrip['company']
                exch = scrip['exchange']

                instrument = Instrument(
                    exch, token, symbol, name, expiry, lot_size)
                master_contract_by_token[token] = instrument
                master_contract_by_symbol[symbol] = instrument
        self.__master_contracts_by_token[exchange] = master_contract_by_token
        self.__master_contracts_by_symbol[exchange] = master_contract_by_symbol

    def get_instrument_by_symbol(self, exchange, symbol):
        """ get instrument by providing symbol """
        # get instrument given exchange and symbol
        exchange = exchange.upper()
        # check if master contract exists
        if exchange not in self.__master_contracts_by_symbol:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_symbol[exchange]
        if symbol not in master_contract:
            logger.warning(
                f"Cannot find symbol {exchange} {symbol} in master contract")
            return None
        return master_contract[symbol]

    def get_instrument_for_fno(self, symbol, expiry_date, is_fut=False, strike=None, is_CE=False, exchange='NFO'):
        """ get instrument for FNO """
        res = self.search_instruments(exchange, symbol)
        if (res == None):
            return
        matches = []
        for i in res:
            sp = i.symbol.split(' ')
            if (sp[0] == symbol):
                if (i.expiry == expiry_date):
                    matches.append(i)
        for i in matches:
            if (is_fut == True):
                if ('FUT' in i.symbol):
                    return i
            else:
                sp = i.symbol.split(' ')
                if ((sp[-1] == 'CE') or (sp[-1] == 'PE')):  # Only option scrips
                    if (float(sp[-2]) == float(strike)):
                        if (is_CE == True):
                            if (sp[-1] == 'CE'):
                                return i
                        else:
                            if (sp[-1] == 'PE'):
                                return i

    def search_instruments(self, exchange, symbol):
        """ Search instrument by symbol match """
        # search instrument given exchange and symbol
        exchange = exchange.upper()
        matches = []
        # check if master contract exists
        if exchange not in self.__master_contracts_by_token:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_token[exchange]
        for contract in master_contract:
            if (isinstance(symbol, list)):
                for sym in symbol:
                    if sym.lower() in master_contract[contract].symbol.split(' ')[0].lower():
                        matches.append(master_contract[contract])
            else:
                if symbol.lower() in master_contract[contract].symbol.split(' ')[0].lower():
                    matches.append(master_contract[contract])
        return matches

    def get_instrument_by_token(self, exchange, token):
        """ Get instrument by providing token """
        # get instrument given exchange and token
        exchange = exchange.upper()
        token = int(token)
        # check if master contract exists
        if exchange not in self.__master_contracts_by_symbol:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_token[exchange]
        if token not in master_contract:
            logger.warning(
                f"Cannot find symbol {exchange} {token} in master contract")
            return None
        return master_contract[token]

    def get_master_contract(self, exchange):
        """ Get master contract """
        return self.__master_contracts_by_symbol[exchange]

    def get_main_limits(self):
        """ Get Detailed balance/margins """
        data = {"token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('detailed_limits', Requests.POST, None, data)

    def get_positions(self):
        """ Get Positions """
        data = {"row_1": "", "row_2": "", "exch": "", "seg": "", "product": "", "v_mode": "", "status": "", "Inst": "",
                "symbol": "", "str_price": "", "place_by": "", "opt_type": "", "exp_dt": "",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('positions', Requests.POST, None, data)

    def get_holdings(self):
        """ Get holdings """
        data = {"row_1": "", "row_2": "",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('holdings', Requests.POST, None, data)

    def get_orders(self):
        """ Get Orders """
        data = {"row_1": "", "row_2": "", "exch": "", "seg": "", "product": "", "status": "", "inst": "",
                "symbol": "", "str_price": "", "place_by": "", "opt_type": "", "exp_dt": "",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('get_orders', Requests.POST, None, data)

    def get_order_info(self, order_id):
        """ Get Order Info """
        df = self.get_orders()
        xyz = find(df, 'ORDER_NUMBER', int(order_id))
        data = {"orderNo": order_id, "seg": df[xyz]['SEGMENT'],
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('get_order_info', Requests.POST, None, data)

    def place_order(self, transaction_type, instrument, InstrumentType, quantity, order_type, product_type, price=0.0,
                    is_amo=False, trigger_price=None):
        """ placing an order, many fields are optional and are not required
                    for all order types
                """
        if transaction_type is None:
            raise TypeError(
                "Required parameter transaction_type not of type TransactionType")

        if not isinstance(instrument, Instrument):
            raise TypeError(
                "Required parameter instrument not of type Instrument")

        if not isinstance(quantity, int):
            raise TypeError("Required parameter quantity not of type int")

        if order_type is None:
            raise TypeError(
                "Required parameter order_type not of type OrderType")

        if product_type is None:
            raise TypeError(
                "Required parameter product_type not of type ProductType")

        if not price or price == 0:
            price = "MKT"
            ord_type = "MKT"
        else:
            price = float(price)
            ord_type = "LMT"

        trigger_price = 0 if not trigger_price else trigger_price

        if (product_type == ProductType.Delivery):
            prod_type = 'M' if instrument.exchange in [
                'NFO', 'MCX', 'CDS'] else 'C'
        else:
            prod_type = 'I'

        exchange = 'NSE' if (instrument.exchange ==
                             "NFO") else instrument.exchange
        # construct order object after all required parameters are met
        data = {"qty": quantity, "price": f"{price}", "odr_type": ord_type, "product_typ": prod_type,
                "trg_prc": trigger_price, "validity": "DAY", "disc_qty": 0, "amo": is_amo, "sec_id": f"{instrument.token}",
                "inst_type": InstrumentType.value, "exch": exchange, "buysell": transaction_type.value,
                "gtdDate": "0000-00-00", "mktProtectionFlag": "N", "mktProtectionVal": 0, "settler": "000000000000",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        print(data)
        resp = self.__api_call_helper('place_order', Requests.POST, None, data)
        return resp['message'].split('.')[-1] if resp['status'] == 'success' else resp

    def place_cover_order(self, transaction_type, instrument, InstrumentType, quantity, order_type,
                          price=0.0, stop_loss=None):
        """ placing an order, many fields are optional and are not required
                    for all order types
                """
        if transaction_type is None:
            raise TypeError(
                "Required parameter transaction_type not of type TransactionType")

        if not isinstance(instrument, Instrument):
            raise TypeError(
                "Required parameter instrument not of type Instrument")

        if not isinstance(quantity, int):
            raise TypeError("Required parameter quantity not of type int")

        if order_type is None:
            raise TypeError(
                "Required parameter order_type not of type OrderType")

        if not price or price == 0:
            price = "MKT"
            ord_type = "MKT"
        else:
            price = float(price)
            ord_type = "LMT"

        stop_loss = 0 if not stop_loss else stop_loss
        exchange = 'NSE' if (instrument.exchange ==
                             "NFO") else instrument.exchange
        # construct order object after all required parameters are met
        data = {"amo": False, "disclosequantity": 0, "securityid": instrument.token, "product_typ": "V",
                "inst_type": InstrumentType.value, "qty": quantity, "price": price, "odr_type": ord_type,
                "buysell": transaction_type.value, "order_validity": "DAY", "exch": exchange,
                "sec_id": instrument.token, "fSLTikAbsValue": stop_loss, "mktProtectionFlag": "N",
                "settler": "000000000000",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}

        data = str(data).replace(" ", "")
        resp = self.__api_call_helper(
            'place_cover_order', Requests.POST, None, data)
        return resp['message'].split('.')[-1] if resp['status'] == 'success' else resp

    def place_bracket_order(self, transaction_type, instrument, InstrumentType, quantity, order_type, trigger_price,
                            stop_loss, target_price, price=0.0):
        """ placing an order, many fields are optional and are not required
                    for all order types """

        if transaction_type is None:
            raise TypeError(
                "Required parameter transaction_type not of type TransactionType")

        if not isinstance(instrument, Instrument):
            raise TypeError(
                "Required parameter instrument not of type Instrument")

        if not isinstance(quantity, int):
            raise TypeError("Required parameter quantity not of type int")

        if order_type is None:
            raise TypeError(
                "Required parameter order_type not of type OrderType")

        if not price or price == 0:
            price = "MKT"
            ord_type = "MKT"
        else:
            price = float(price)
            ord_type = "LMT"

        stop_loss = 0 if not stop_loss else stop_loss

        exchange = 'NSE' if (instrument.exchange ==
                             "NFO") else instrument.exchange
        # construct order object after all required parameters are met
        data = {"amo": False, "disclosequantity": 0, "securityid": instrument.token, "productlist": "B",
                "inst_type": InstrumentType.value, "iNoOfLeg": "3", "qty": quantity, "price": price,
                "odr_type": ord_type, "buysell": transaction_type.value, "order_validity": "DAY",
                "exch": exchange, "sec_id": instrument.token, "fPBTikAbsValue": target_price,
                "fSLTikAbsValue": stop_loss, "fTrailingSLValue": 0, "mktProtectionFlag": "N",
                "trg_prc": trigger_price, "settler": "000000000000",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}

        data = str(data).replace(" ", "")
        resp = self.__api_call_helper(
            'place_bracket_order', Requests.POST, None, data)
        return resp['message'].split('.')[-1] if resp['status'] == 'success' else resp

    def modify_order(self, order_id, order_type: OrderType, quantity=None, price=0.0, trigger_price=0.0, is_amo=False):
        """ Cancel single order """
        ord_dict = {'INTRADAY': 'I', 'MARGIN': 'M',
                    'DELIVERY': 'C', 'COVERORDER': 'V', 'BRACKETORDER': 'B'}
        ord_type = {'MARKET': 'MKT', 'LIMIT': 'LMT',
                    'SL': 'SL', 'SL-M': 'SL-M'}
        df = self.get_orders()
        xyz = find(df, 'ORDER_NUMBER', int(order_id))
        sec_id = df[xyz]['SEM_SECURITY_ID']
        order_info = self.get_order_info(order_id=order_id)[0]
        quantity = order_info.get("ORD_QTY_ORIGINAL", quantity)

        data = {"exch": order_info['ORD_EXCH_ID'], "serialno": order_info['ORD_SERIAL_NO'], "orderno": order_id,
                "scripname": order_info['SEM_SYMBOL'], "buysell": order_info['ORD_BUY_SELL_IND'], "qty_type": order_type.value,
                "qty": quantity, "prc": price, "trg_prc": trigger_price, "disc_qty": order_info['DISCLOSE_QTY'],
                "productlist": ord_dict[order_info['PRODUCT']], "order_typ": order_info['ORDER_VALIDITY'], "sec_id": f"{sec_id}",
                "qty_rem": quantity, "inst_type": order_info['INSTRUMENT'], "amo": is_amo, "trd_qty": order_info['ORD_QTY_TRADED'],
                "status": order_info['STATUS'], "gtdDate": "0000-00-00", "mktProtectionFlag": "N", "mktProtectionVal": 0,
                "settler": "000000000000",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}

        data = str(data).replace(" ", "")
        resp = self.__api_call_helper(
            'modify_order', Requests.POST, None, data)
        return resp['message'].split('.')[-1] if resp['status'] == 'success' else resp

    def cancel_order(self, order_id):
        """ Cancel single order """
        ord_dict = {'INTRADAY': 'I', 'MARGIN': 'M',
                    'DELIVERY': 'C', 'COVERORDER': 'V', 'BRACKETORDER': 'B'}
        ord_type = {'MARKET': 'MKT', 'LIMIT': 'LMT',
                    'SL': 'SL', 'SL-M': 'SL-M'}
        df = self.get_orders()
        xyz = find(df, 'ORDER_NUMBER', int(order_id))
        sec_id = df[xyz]['SEM_SECURITY_ID']
        df = self.get_order_info(order_id=order_id)[0]
        data = {"exch": df['ORD_EXCH_ID'], "serialno": df['ORD_SERIAL_NO'], "orderno": order_id,
                "scripname": df['SEM_SYMBOL'], "buysell": df['ORD_BUY_SELL_IND'],
                "qty_type": ord_type[df['ORDER_TYPE']], "qty": df['ORD_QTY_ORIGINAL'],
                "prc": df['PRICE'], "trg_prc": df['TRG_PRICE'], "disc_qty": df['DISCLOSE_QTY'],
                "productlist": ord_dict[df['PRODUCT']], "order_typ": df['ORDER_VALIDITY'], "sec_id": f"{sec_id}",
                "qty_rem": df['ORD_QTY_REMAINING'], "inst_type": df['SEGMENT'],
                "offline_flag": True, "gtdDate": "0000-00-00", "settler": "000000000000",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        resp = self.__api_call_helper(
            'cancel_order', Requests.POST, None, data)
        return resp['message'].split('.')[-1] if resp['status'] == 'success' else resp

    def get_trade_book(self):
        """ get all trades """
        data = {"row_1": "", "row_2": "", "exch": "", "seg": "", "product": "", "status": "", "symbol": "", "cl_id": "",
                "place_by": "", "str_price": "",
                "token_id": self.__tokenid, "keyid": self.__keyid, "userid": self.__username,
                "clienttype": self.__usertype, "usercode": self.__usercode, "pan_no": self.__panno}
        data = str(data).replace(" ", "")
        return self.__api_call_helper('trade_book', Requests.POST, None, data)

    def __api_call_helper(self, name, http_method, params, data):
        # helper formats the url and reads error codes nicely
        config = self.__service_config
        url = f"{config['host']}{config['routes'][name]}"
        if params is not None:
            url = url.format(**params)
        response = self.__api_call(url, http_method, data)
        if response.status_code != 200:
            raise requests.HTTPError(response.text)
        return json.loads(response.text)

    def __api_call(self, url, http_method, data):
        # logger.debug('url:: %s http_method:: %s data:: %s headers:: %s', url, http_method, data, headers)
        config = Shoonya.__service_config
        headers = config['headers']
        headers['Authorisation'] = self.__access_token
        r = None
        if http_method is Requests.POST:
            r = requests.post(url, data=data, headers=headers)
        elif http_method is Requests.DELETE:
            r = requests.delete(url, headers=headers)
        elif http_method is Requests.PUT:
            r = requests.put(url, data=data, headers=headers)
        elif http_method is Requests.GET:
            r = requests.get(url, headers=headers)
        return r
