import http.client
import logging
import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    actor_login = fields.Char("Login (pods)")
    actor_token = fields.Char("Token")

    def get_inbox(self):
        conn = http.client.HTTPSConnection("ap.octr.ee")
        payload = ""
        actor_login = self.env.user.company_id.actor_login
        actor_token = self.env.user.company_id.actor_token
        headers = { 'Authorization': "Bearer %s " % actor_token }
        conn.request("GET", "/%s/inbox?page=1" % actor_login, payload, headers)
        res = conn.getresponse()
        _logger.debug("res: %s" % res)
        data = res.read()
        product_obj = self.env["product.template"]
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1
        )
        _logger.debug(data.decode("utf-8"))
        my_inbox = json.loads(data.decode("utf-8"))
        for activity in my_inbox['orderedItems']:
            _logger.debug(activity)
            if activity["type"] == "Announce":
                current_product = product_obj.search([("offer_uri", "=", activity["object"])])
                if not current_product:
                    conn.request("GET", activity["object"], payload, headers)
                    offer = conn.getresponse()
                    offer_data = json.loads(offer.read().decode("utf-8"))
                    current_product = product_obj.create({
                        "name": offer_data["schema:name"],
                        "list_price": offer_data["schema:price"],
                        "detailed_type": "product",
                        "offer_uri": activity["object"],
                        "website_published": True,
                    })
                    self.env['stock.quant'].with_context(inventory_mode=True).create({
                        'product_id': current_product.product_variant_id.id,
                        'location_id': warehouse.lot_stock_id.id,
                        'inventory_quantity': offer_data["schema:eligibleQuantity"]["schema:value"],
                    })._apply_inventory()
                    _logger.debug("Offer: %s" % offer_data["schema:name"])