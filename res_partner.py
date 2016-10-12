# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
import re
import unicodedata
try:
    from openerp import models, fields
    from openerp import SUPERUSER_ID
    from openerp.tools.translate import _
    from openerp.tools import email_split, single_email_re
    from openerp.tools import ustr
except:
    from odoo import models, fields
    from odoo import SUPERUSER_ID
    from odoo.tools.translate import _
    from odoo.tools import email_split, single_email_re
    from odoo.tools import ustr
import string
import random


def extract_email(email):
    """ extract the email address from a user-friendly email address """
    addresses = email_split(email)
    return addresses[0] if addresses else ''

# Inspired by http://stackoverflow.com/questions/517923


def remove_accents(input_str):
    """Suboptimal-but-better-than-nothing way to replace accented
    latin letters by an ASCII equivalent. Will obviously change the
    meaning of input_str and work only for some cases"""
    input_str = ustr(input_str)
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u''.join([c for c in nkfd_form if not unicodedata.combining(c)])


class partner(models.Model):

    """"""

    _inherit = 'res.partner'

    def _retrieve_user(self, context=None):
        """ retrieve the (possibly inactive) user corresponding to wizard_user.partner_id
            @param wizard_user: browse record of model portal.wizard.user
            @return: browse record of model res.users
        """
        context = dict(context or {}, active_test=False)
        res_users = self.env['res.users']
        res = {}
        for i in self:
            domain = [('partner_id', '=', i)]
            user_ids = res_users.search(domain)
            user_id = False
            if user_ids:
                user_id = user_ids[0]
            res[i] = user_id
        return res

    login = fields.Char(related='user_id.login', string='Login',
                            help="Used to log into the system", store=True)
    # password = fields.Char(related='related_user_id.password', string='Password', size=64, readonly=True,
    #                            help="Keep empty if you don't want the user to be able to connect on the system.")
    related_user_id = fields.Many2one('res.users', compute='_retrieve_user', string='User', type='many2one',store=True)
    template_user_id = fields.Many2one('res.users', string="Template User", domain=[('active', '=', False)])

    def open_related_user(self, cr, uid, ids, context=None):
        # user_id = self.browse(
        #     cr, uid, ids[0], context=context).related_user_id.id
        user_id = self.related_user_id.id
        if not user_id:
            return False
        view_ref = self.env['ir.model.data'].get_object_reference('base', 'view_users_form')
        view_id = view_ref and view_ref[1] or False,
        return {
            'type': 'ir.actions.act_window',
            'view_id': view_id,
            'res_model': 'res.users',
            'view_mode': 'form',
            'res_id': user_id,
            'target': 'current',
            # 'flags': {'form': {'action_buttons': True, 'options': {'mode': 'edit'}}}
        }

    def delete_user(self):
        # user_id = self.browse(
        #     cr, uid, ids[0], context=context).related_user_id.id
        user_id = self.related_user_id.id
        if not user_id:
            return False
        return self.env['res.users'].unlink([user_id])

    def retrieve_user(self,partner):
        """ retrieve the (possibly inactive) user corresponding to partner
            @param partner: browse record of model portal.wizard.user
            @return: browse record of model res.users
        """

        # context = dict(context or {}, active_test=False)
        res_users = self.env['res.users']
        domain = [('partner_id', '=', partner.id)]
        user_ids = res_users.search(domain)
        return user_ids

    def quickly_create_user(self):
        res_users = self.env['res.users']
        # Make this an option
        # context = dict(context or {}, no_reset_password=True)
        # TODO Pasar argumentos para activar o desactivar
        create_user = True

        for partner in self:
            group_ids = []
            # if not partner.template_user_id:
            #     raise osv.except_osv(_('Non template user selected!'),
            #                          _('Please define a template user for this partner: "%s" (id:%d).') % (partner.name, partner.id))
            # group_ids = [x.id for x in partner.template_user_id.groups_id]
            user_ids = self.retrieve_user(partner)
            if create_user:
                # create a user if necessary, and make sure it is in the portal
                # group
                if not user_ids:
                    user_ids = [
                        self._create_user(partner)]
                # res_users.write(
                #     cr, SUPERUSER_ID, user_ids, {'active': True, 'groups_id': [(6, 0, group_ids)]})
                # prepare for the signup process
                # TODO make an option of this
                # partner.signup_prepare()
                # TODO option to send or not email
                # self._send_email(cr, uid, partner, context)
            elif user_ids:
                # deactivate user
                res_users.write(user_ids, {'active': False})

    def _create_user(self):
        """ create a new user for partner.partner_id
            @param partner: browse record of model partner.user
            @return: browse record of model res.users
        """
        res_users = self.env['res.users']
        # to prevent shortcut creation
        create_context = dict(
            self.contex or {}, noshortcut=True, no_reset_password=True, signup_valid=True,create_user=True)
        if partner.email and single_email_re.match(partner.email):
            login = extract_email(partner.email)
        else:
            login = self._clean_and_make_unique(partner.name)
        values = {
            # 'email': extract_email(partner.email),
            'login': login,
            # 'login': extract_email(partner.email),

            'partner_id': partner.id,
            'company_id': partner.company_id.id,
            'company_ids': [(4, partner.company_id.id)],
        }
        user = res_users.create(values, context=create_context)
        if user:
            res_users.action_reset_password(user, context=create_context)
        return

    def _clean_and_make_unique(self, name, context=None):
        # when an alias name appears to already be an email, we keep the local
        # part only
        name = remove_accents(name).lower().split('@')[0]
        name = re.sub(r'[^\w+.]+', '.', name)
        return self._find_unique(name, context=context)

    def _find_unique(self, name, context=None):
        """Find a unique alias name similar to ``name``. If ``name`` is
           already taken, make a variant by adding an integer suffix until
           an unused alias is found.
        """
        sequence = None
        while True:
            new_name = "%s%s" % (
                name, sequence) if sequence is not None else name
            if not self.env['res.users'].search([('login', '=', new_name)]):
                break
            sequence = (sequence + 1) if sequence else 2
        return new_name

