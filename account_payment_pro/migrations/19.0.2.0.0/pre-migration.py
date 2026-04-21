import logging
import json
import re

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migración account_payment_pro 19.0.2.0.0
    Elimina campos obsoletos del arch_db de vistas de pagos:
    - payment_total
    - payment_method_description
    """
    _logger.info("account_payment_pro pre-migrate: limpiando campos obsoletos")

    campos = ['payment_total', 'payment_method_description']
    vistas = [
        ('account_payment_pro', 'view_account_payment_tree'),
        ('account_payment_pro', 'view_account_payment_form'),
    ]

    for module, xmlid in vistas:
        cr.execute("""
            SELECT id, arch_db FROM ir_ui_view
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = %s
                  AND name = %s
                  AND model = 'ir.ui.view'
            )
            AND (
                arch_db::text LIKE '%%payment_total%%'
                OR arch_db::text LIKE '%%payment_method_description%%'
            )
        """, (module, xmlid))
        row = cr.fetchone()
        if row:
            view_id, arch_db = row
            arch_dict = dict(arch_db)
            modified = False
            for lang in arch_dict:
                for campo in campos:
                    if campo in arch_dict[lang]:
                        arch_dict[lang] = re.sub(
                            rf'<field[^>]*name="{campo}"[^>]*/>',
                            '', arch_dict[lang]
                        )
                        modified = True
            if modified:
                cr.execute(
                    "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                    [json.dumps(arch_dict), view_id]
                )
                _logger.info(f"  ✓ {module}.{xmlid} corregida (id {view_id})")
        else:
            _logger.info(f"  - {module}.{xmlid} ya está limpia")
