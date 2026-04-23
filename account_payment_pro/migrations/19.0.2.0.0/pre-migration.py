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
    Y limpieza global de <setting> obsoletos en res.config.settings
    que causan fallo al validar res_company_setting.xml al cargar el módulo.
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

    # Desactivar vista de account_accountant_ux si tiene campo obsoleto
    # (se limpia en el post-migrate de account_accountant_ux y se reactiva)
    # Este fix puede removerse cuando el daily backup ya tenga la vista limpia
    cr.execute("""
        UPDATE ir_ui_view SET active = False
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'account_accountant_ux'
              AND name = 'res_config_settings_view_form'
              AND model = 'ir.ui.view'
        )
        AND arch_db::text LIKE '%use_company_currency_on_followup%'
    """)
    if cr.rowcount > 0:
        _logger.info("  ✓ account_accountant_ux.res_config_settings_view_form desactivada temporalmente")

    # -------------------------------------------------------------------
    # Limpieza global de <setting> obsoletos en res.config.settings.
    # Acá porque account_payment_pro es el módulo cuyo XML (res_company_setting.xml)
    # falla al validar la vista combinada si estas <setting> están en cualquier
    # vista heredada. Busca por contenido del arch_db, sin depender de IDs
    # hardcodeados ni de xmlids específicos.
    # -------------------------------------------------------------------
    _logger.info("account_payment_pro pre-migrate: limpieza global de <setting> obsoletos")

    settings_obsoletos = [
        'use_search_filter_amount',
        'company_currency_on_follow_up',
    ]

    for setting_id in settings_obsoletos:
        cr.execute("""
            UPDATE ir_ui_view
            SET arch_db = CAST(
                regexp_replace(
                    arch_db::text,
                    '<setting id="' || %s || '"[^<]*(<[^/][^>]*>[^<]*</[^>]*>|<[^/][^>]*/?>)*[^<]*</setting>',
                    '',
                    'g'
                ) AS jsonb
            )
            WHERE arch_db::text LIKE '%%' || %s || '%%'
        """, (setting_id, setting_id))
        _logger.info(f"  ✓ {setting_id}: {cr.rowcount} vistas procesadas")