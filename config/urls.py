from django.contrib.auth import views as auth_views
from django.urls import path
from cemetery import views

urlpatterns = [
    path("salud/", views.health, name="health"),
    path("ingresar/", views.sign_in, name="login"),
    path("registro/", views.family_register, name="family_register"),
    path("registro/reenviar/", views.family_resend_verification, name="family_resend"),
    path("privacidad/", views.family_privacy_notice, name="family_privacy"),
    path("registro/verificar/<uidb64>/<token>/", views.family_verify, name="family_verify"),
    path("mi-cuenta/", views.family_portal, name="family_portal"),
    path("mi-cuenta/recibos/<int:pk>/", views.family_receipt, name="family_receipt"),
    path("mi-cuenta/documentos/<int:document_pk>/", views.family_document_download, name="family_document_download"),
    path("gestion/cuentas-familiares/", views.family_accounts, name="family_accounts"),
    path("salir/", views.sign_out, name="logout"),
    path(
        "recuperar/",
        views.RecoverAccessView.as_view(
            template_name="registration/reset.html",
            email_template_name="registration/reset_email.txt",
            subject_template_name="registration/reset_subject.txt",
            success_url="/recuperar/enviado/",
        ),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "recuperar/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/completado/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("", views.dashboard, name="dashboard"),
    path("mapa/", views.cemetery_map, name="map"),
    path("mapa/fondo/", views.map_plan_manage, name="map_plan_manage"),
    path("mapa/fondo/imagen.png", views.map_plan_image, name="map_plan_image"),
    path("mapa/coordenadas/", views.map_coordinates, name="map_coordinates"),
    path("mapa/coordenadas.csv", views.map_coordinates_csv, name="map_coordinates_csv"),
    path("sepulturas/importar/", views.space_import, name="space_import"),
    path("sepulturas/importar/plantilla.csv", views.space_import_csv, name="space_import_csv"),
    path("sepulturas/exportar.csv", views.space_export_csv, name="space_export_csv"),
    path("reportes/capacidad/", views.space_capacity_report, name="space_capacity_report"),
    path("mapa/sepultura/<int:pk>/coordenada/", views.map_coordinate_update, name="map_coordinate_update"),
    path("mapa/datos/", views.map_data, name="map_data"),
    path("sepultura/<int:pk>/", views.space_detail, name="space_detail"),
    path("sepultura/<int:pk>/condicion/", views.condition, name="condition"),
    path("persona/<int:pk>/", views.person_detail, name="person_detail"),
    path("auditoria/<int:pk>/", views.audit_detail, name="audit_detail"),
    path("demostracion/correos/", views.academic_mailbox, name="academic_mailbox"),
    path("contrato/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contrato/<int:pk>/imprimir/", views.contract_print, name="contract_print"),
    path("contrato/<int:pk>/documentos/subir/", views.contract_document_upload, name="contract_document_upload"),
    path("contrato/<int:pk>/documentos/<int:document_pk>/", views.contract_document_download, name="contract_document_download"),
    path("gasto/<int:pk>/", views.expense_detail, name="expense_detail"),
    path("gasto/<int:pk>/documentos/subir/", views.expense_document_upload, name="expense_document_upload"),
    path("gasto/<int:pk>/documentos/<int:document_pk>/", views.expense_document_download, name="expense_document_download"),
    path("factura/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("finanzas/cartera/", views.finance_portfolio, name="finance_portfolio"),
    path("finanzas/libro-caja/", views.finance_cashbook, name="finance_cashbook"),
    path("reserva/<int:pk>/", views.reservation_detail, name="reservation_detail"),
    path("reservas/<int:reservation_pk>/pagos/<int:payment_pk>/devoluciones/", views.reservation_refund, name="reservation_refund"),
    path("pago/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("devolucion/<int:pk>/", views.refund_detail, name="refund_detail"),
    path("movimiento/<int:pk>/", views.movement_detail, name="movement_detail"),
    path("vincular-responsable/", views.link_person, name="link_person"),
    path("inhumacion/", views.burial, name="burial"),
    path("gestion/<str:kind>/", views.listing, name="listing"),
    path("gestion/<str:kind>/nuevo/", views.edit_record, name="new_record"),
    path("gestion/<str:kind>/<int:pk>/editar/", views.edit_record, name="edit_record"),
    path("accion/<str:kind>/<int:pk>/<str:action_name>/", views.action, name="action"),
]
