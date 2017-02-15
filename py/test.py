# -*- coding:utf-8 -*-
import sys 
import json
import time
sys.path.append("../")

from jingtumsdk.server import APIServer, WebSocketServer, TumServer, Server
from jingtumsdk.account import Wallet, FinGate, Amount
from jingtumsdk.logger import logger
from jingtumsdk.operation import PaymentOperation, OrderOperation, CancelOrderOperation


def get_cfg_from_json(file_name="test_data.json"):
    f = open(file_name)
    ff = f.read()
    cfg_data = json.loads(ff)
    f.close()
    return cfg_data

cfg_data = get_cfg_from_json()

# root account just for test
test_address = str(cfg_data["DEV"]["fingate1"]["address"])
test_secret = str(cfg_data["DEV"]["fingate1"]["secret"])
test_issuer = "jBciDE8Q3uJjf111VeiUNM775AMKHEbBLS"

# ulimit account just for test
test_ulimit_address = str(cfg_data["DEV"]["fingate1"]["address"])
test_ulimit_secret = str(cfg_data["DEV"]["fingate1"]["secret"])
# FinGate account just for test
ekey = str(cfg_data["DEV"]["fingate1"]["sign_key"])
custom = str(cfg_data["DEV"]["fingate1"]["custom_id"])
test_currency = str(cfg_data["DEV"]["fingate1"]["tum1"])


# init FinGate
fingate = FinGate()
fingate.setMode(FinGate.DEVLOPMENT)
fingate.setAccount(test_secret, test_address)
fingate.setActivateAmount(10)

# sys.exit(0)

#tongtong testing
fingate.setToken(custom)
fingate.setKey(ekey)
order = fingate.getNextUUID()
ret = fingate.issueCustomTum(test_currency, "123.45", order, test_ulimit_address)
logger.info("issueCustomTum:" + str(ret))

logger.info("queryIssue:" + str(fingate.queryIssue(order)))

ret = fingate.queryCustomTum(test_currency)
logger.info("queryCustomTum:" + str(fingate.queryIssue(order)))

#sys.exit(0)

# init test wallet
master_wallet = Wallet(test_secret, test_address)
master_unlimit_wallet = Wallet(test_ulimit_secret, test_ulimit_address)


class WalletClient(Wallet):
    def __init__(self, wallet):
        super(WalletClient, self).__init__(wallet.secret, wallet.address)
        self.wallet_status = 0
        
        self.last_order_hash = None
        self.last_resource_id = None

        self.isActivated = False

        self.address = wallet.address
        self.secret = wallet.secret
        self.my_wallet = wallet
        
    def active_callback(self, res):
        logger.info("active_callback:::::" + str(res))

    def payment_callback(self, res):
        logger.info("payment_callback:::::" + str(res))
        self.set_last_resource_id(res["client_resource_id"])

    def createorder_callback(self, res):
        logger.info("createorder_callback:::::" + str(res))

    def cancelorder_callback(self, res):
        logger.info("cancelorder_callback:::::" + str(res))

    def getorderbook_callback(self, res):
        logger.info("getorderbook_callback:::::" + str(res))

    def set_wallet_status(self, status):
        self.wallet_status = status

    def get_wallet_status(self):
        return self.wallet_status

    def set_last_order_hash(self, hash_id):
        self.last_order_hash = hash_id

    def set_last_resource_id(self, resource_id):
        self.last_resource_id = resource_id

    def on_ws_receive(self, data, *arg):
        logger.info("do_socket_receive0")

        if data.has_key("success") and data["success"]:
            if self.my_wallet and data.has_key("type") and data["type"] == "Payment":
                ret = self.my_wallet.getBalance()
                print "2333333", ret
                self.isActivated = True
                if self.get_wallet_status() == 0:
                    self.set_wallet_status(1)
                elif self.get_wallet_status() == 2:
                    self.set_wallet_status(3) #3
            elif data.has_key("type") and data["type"] == "OfferCreate":
                logger.info("offer created:" + str(data) + str(arg))

                # set last order hash for next test
                if data.has_key("transaction"):
                    self.set_last_order_hash(data["transaction"]["hash"])

                self.set_wallet_status(6)
            elif data.has_key("type") and data["type"] == "OfferCancel":
                logger.info("offer canceled:" + str(data) + str(arg))
                self.set_wallet_status(8)
            elif data.has_key("type") and data["type"] == "TrustSet":
                logger.info("trust seted:" + str(data) + str(arg))
                self.set_wallet_status(14)
            else:
                logger.info("do_socket_receive:" + str(data) + str(arg))


# create my wallet
my_wallet = None
my_wallet = WalletClient(fingate.createWallet())
logger.info(fingate.activeWallet(my_wallet.address, callback=my_wallet.active_callback))

# websocket init and subscribe
ws = WebSocketServer()
ws.subscribe(my_wallet.address, my_wallet.secret)

# register ws callback
ws.setTxHandler(my_wallet.on_ws_receive)

while 1:
    #print "while ing... ... ..."
    if my_wallet and my_wallet.isActivated:
        r = my_wallet.getOrderList()
        logger.info("get Order List:" + str(r["orders"]))
        sys.exit(0)
	if my_wallet.get_wallet_status() == 1: # USD payment, from ulimit wallet to my wallet
            usd = PaymentOperation(master_unlimit_wallet)
            amt = Amount(10, "CNY", test_issuer)
            usd.setAmount(amt)
            usd.setDestAddress(my_wallet.address)
            usd.setValidate(True)
            ret = usd.submit(callback=my_wallet.payment_callback)
            if ret is not None and ret.has_key("success") and ret["success"]:
                my_wallet.set_last_resource_id(ret["client_resource_id"])
            my_wallet.set_wallet_status(2)
        elif my_wallet.get_wallet_status() == 3:
            r = my_wallet.getPayment(my_wallet.last_resource_id)
            logger.info("get_payment test:" + str(r))
            options = {"destination_account": my_wallet.getAddress(), "results_per_page": "3", "page": "1"}
            r = my_wallet.getPaymentList(options=options)
            logger.info("get_payments test:" + str(r))    
            my_wallet.set_wallet_status(4)
        elif my_wallet.get_wallet_status() == 4:
            amt = Amount("1.00", "CNY", issuer=test_issuer)
            r = my_wallet.getChoices(my_wallet.address, amt)
            logger.info("get_paths test:" + str(r))
            
            # create order
            co = OrderOperation(my_wallet)
            co.setPair("SWT/CNY:%s"%test_issuer);
            co.setType(OrderOperation.SELL);
            co.setAmount(20.00);
            co.setPrice(0.5);
            co.submit(callback=my_wallet.createorder_callback)

            my_wallet.set_wallet_status(5)
        elif my_wallet.get_wallet_status() == 6:
            r = my_wallet.getOrderList()
            logger.info("get_account_orders test:" + str(r))
            # pair = "SWT/CNY:jBciDE8Q3uJjf111VeiUNM775AMKHEbBLS"
            # r = fingate.getOrderBook(pair, callback=my_wallet.getorderbook_callback)
            # logger.info("get_order_book test:" + str(r))

            # cancel order
            co = CancelOrderOperation(my_wallet)
            co.setSequence(1)
            r = co.submit(callback=my_wallet.cancelorder_callback)
            logger.info("cancel_order 1 test:" + str(r))
            my_wallet.set_wallet_status(7) #7
        elif my_wallet.get_wallet_status() == 8:
            if my_wallet.last_order_hash is not None:
                r = my_wallet.getOrder(my_wallet.last_order_hash)
                logger.info("get_order_by_hash test:" + str(r))
            my_wallet.set_wallet_status(9)
        elif my_wallet.get_wallet_status() == 9:
            if my_wallet.last_order_hash is not None:
                r = my_wallet.getTransaction(my_wallet.last_order_hash)
                logger.info("retrieve_order_transaction test:" + str(r))
            options = {"destination_account": my_wallet.getAddress(), "page": "1"}
            r = my_wallet.getTransactionList(options=options)
            logger.info("order_transaction_history test:" + str(r))
            my_wallet.set_wallet_status(10)


    time.sleep(2)
    pass
