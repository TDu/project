# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, models, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):

    _inherit = 'account.analytic.line'

    @api.model
    def create(self, vals):
        employee = None
        if 'employee_id' in vals:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
        elif self.env.user.employee_ids:
            employee = self.env.user.employee_ids[0]

        if employee and 'project_id' in vals:
            if not employee.seniority_level_id:
                raise UserError(
                    _('''Employee with no seniority level can not timesheet
                         on project, contact your HR department.
                      '''
                      )
                )
            project = self.env['project.project'].browse(vals['project_id'])
            # check for existing mapping in project configuration
            employee_mapped_line = project.sale_line_employee_ids.filtered(
                lambda r: r.employee_id.id == employee.id
            )
            if not employee_mapped_line:
                # Find a line on the sale order with the same seniority level
                so = project.sale_order_id
                sol = so.order_line.filtered(
                    lambda r: r.product_id.seniority_level_id
                    == employee.seniority_level_id
                )
                if not sol:
                    # No product on the sale order  with the same seniority
                    # level than the employee.
                    any_product = self.env['product.template'].search(
                        [
                            (
                                'seniority_level_id',
                                '=',
                                employee.seniority_level_id.id,
                            )
                        ],
                        limit=1,
                    )
                    if not any_product:
                        raise UserError(
                            _('No product exists with this seniority level.')
                        )
                    # Adding any product with the same seniority level
                    so.write(
                        {
                            'order_line': [
                                (
                                    0,
                                    False,
                                    {
                                        'product_id': any_product.id,
                                        'product_uom_qty': 0,
                                    },
                                )
                            ]
                        }
                    )
                    so_line = so.order_line.filtered(
                        lambda r: r.product_id.id == any_product.id
                    )
                    # Alert Salesman
                    self.env['mail.activity'].create({
                        'res_id': so.id,
                        'res_model_id': self.env.ref(
                            'sale.model_sale_order').id,
                        'activity_type_id': 4,
                        'user_id': so.user_id.id,
                        'summary': _(
                            'Please check the product {} for {}'.format(
                                any_product.name, employee.name)),
                    })
                else:
                    so_line = sol[0]
                # Create that missing mapped line
                project.write(
                    {
                        'sale_line_employee_ids': [
                            (
                                0,
                                False,
                                {
                                    'employee_id': employee.id,
                                    'sale_line_id': so_line.id,
                                },
                            )
                        ]
                    }
                )

        return super().create(vals)