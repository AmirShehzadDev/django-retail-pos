from django.urls import path

from . import checkout_views, views

app_name = "sales"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("start/", views.start_workspace_view, name="start_workspace"),
    path("drafts/new/", views.draft_create, name="draft_create"),
    path("drafts/<int:draft_id>/scan/", views.draft_scan, name="draft_scan"),
    path(
        "drafts/<int:draft_id>/products/add/",
        views.draft_add_product,
        name="draft_add_product",
    ),
    path(
        "drafts/<int:draft_id>/quick-create/",
        views.quick_create,
        name="quick_create",
    ),
    path(
        "drafts/<int:draft_id>/items/<int:item_id>/quantity/",
        views.item_quantity,
        name="item_quantity",
    ),
    path(
        "drafts/<int:draft_id>/items/<int:item_id>/remove/",
        views.item_remove,
        name="item_remove",
    ),
    path(
        "drafts/<int:draft_id>/takeover/",
        views.draft_takeover,
        name="draft_takeover",
    ),
    path(
        "drafts/<int:draft_id>/clear/",
        views.draft_clear,
        name="draft_clear",
    ),
    path(
        "drafts/<int:draft_id>/close/",
        views.draft_close,
        name="draft_close",
    ),
    path(
        "drafts/<int:draft_id>/checkout/",
        checkout_views.checkout,
        name="checkout",
    ),
]
