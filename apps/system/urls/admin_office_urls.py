from django.urls import path
from apps.system.views import admin_office_views

app_name = 'admin_office'

urlpatterns = [
    # 公告管理路由
    path('notice/', admin_office_views.NoticeListView.as_view(), name='notice_list'),
    path('notice/create/', admin_office_views.NoticeCreateView.as_view(), name='notice_create'),
    path('notice/update/<int:pk>/', admin_office_views.NoticeUpdateView.as_view(), name='notice_update'),
    path('notice/delete/<int:pk>/', admin_office_views.NoticeDeleteView.as_view(), name='notice_delete'),
    path('notice/detail/<int:pk>/', admin_office_views.NoticeDetailView.as_view(), name='notice_detail'),
    path('notice/publish/<int:pk>/', admin_office_views.NoticePublishView.as_view(), name='notice_publish'),
    
    # 会议室管理路由
    path('meeting_room/', admin_office_views.MeetingRoomListView.as_view(), name='meeting_room_list'),
    path('meeting_room/create/', admin_office_views.MeetingRoomCreateView.as_view(), name='meeting_room_create'),
    path('meeting_room/update/<int:pk>/', admin_office_views.MeetingRoomUpdateView.as_view(), name='meeting_room_update'),
    path('meeting_room/delete/<int:pk>/', admin_office_views.MeetingRoomDeleteView.as_view(), name='meeting_room_delete'),
    
    # 会议室预订路由
    path('meeting_reservation/', admin_office_views.MeetingReservationListView.as_view(), name='meeting_reservation_list'),
    path('meeting_reservation/create/', admin_office_views.MeetingReservationCreateView.as_view(), name='meeting_reservation_create'),
    path('meeting_reservation/update/<int:pk>/', admin_office_views.MeetingReservationUpdateView.as_view(), name='meeting_reservation_update'),
    path('meeting_reservation/delete/<int:pk>/', admin_office_views.MeetingReservationDeleteView.as_view(), name='meeting_reservation_delete'),
    path('meeting_reservation/approve/<int:pk>/', admin_office_views.MeetingReservationApproveView.as_view(), name='meeting_reservation_approve'),
    path('meeting_reservation/reject/<int:pk>/', admin_office_views.MeetingReservationRejectView.as_view(), name='meeting_reservation_reject'),
    
    # 印章管理路由
    path('seal/', admin_office_views.SealListView.as_view(), name='seal_list'),
    path('seal/create/', admin_office_views.SealCreateView.as_view(), name='seal_create'),
    path('seal/update/<int:pk>/', admin_office_views.SealUpdateView.as_view(), name='seal_update'),
    path('seal/delete/<int:pk>/', admin_office_views.SealDeleteView.as_view(), name='seal_delete'),
    
    # 印章申请路由
    path('seal_application/', admin_office_views.SealApplicationListView.as_view(), name='seal_application_list'),
    path('seal_application/create/', admin_office_views.SealApplicationCreateView.as_view(), name='seal_application_create'),
    path('seal_application/update/<int:pk>/', admin_office_views.SealApplicationUpdateView.as_view(), name='seal_application_update'),
    path('seal_application/delete/<int:pk>/', admin_office_views.SealApplicationDeleteView.as_view(), name='seal_application_delete'),
    path('seal_application/approve/<int:pk>/', admin_office_views.SealApplicationApproveView.as_view(), name='seal_application_approve'),
    path('seal_application/reject/<int:pk>/', admin_office_views.SealApplicationRejectView.as_view(), name='seal_application_reject'),
    
    # 公文管理路由
    path('document/', admin_office_views.DocumentListView.as_view(), name='document_list'),
    path('document/create/', admin_office_views.DocumentCreateView.as_view(), name='document_create'),
    path('document/update/<int:pk>/', admin_office_views.DocumentUpdateView.as_view(), name='document_update'),
    path('document/delete/<int:pk>/', admin_office_views.DocumentDeleteView.as_view(), name='document_delete'),
    path('document/detail/<int:pk>/', admin_office_views.DocumentDetailView.as_view(), name='document_detail'),
    path('document/submit/<int:pk>/', admin_office_views.DocumentSubmitView.as_view(), name='document_submit'),
    path('document/approve/<int:pk>/', admin_office_views.DocumentApproveView.as_view(), name='document_approve'),
    path('document/reject/<int:pk>/', admin_office_views.DocumentRejectView.as_view(), name='document_reject'),
    path('document/publish/<int:pk>/', admin_office_views.DocumentPublishView.as_view(), name='document_publish'),
    
    # 公文分类管理路由
    path('document_category/', admin_office_views.DocumentCategoryListView.as_view(), name='document_category_list'),
    path('document_category/create/', admin_office_views.DocumentCategoryCreateView.as_view(), name='document_category_create'),
    path('document_category/update/<int:pk>/', admin_office_views.DocumentCategoryUpdateView.as_view(), name='document_category_update'),
    path('document_category/delete/<int:pk>/', admin_office_views.DocumentCategoryDeleteView.as_view(), name='document_category_delete'),
    
    # 资产设备管理路由
    path('asset/', admin_office_views.AssetListView.as_view(), name='asset_list'),
    path('asset/create/', admin_office_views.AssetCreateView.as_view(), name='asset_create'),
    path('asset/update/<int:pk>/', admin_office_views.AssetUpdateView.as_view(), name='asset_update'),
    path('asset/delete/<int:pk>/', admin_office_views.AssetDeleteView.as_view(), name='asset_delete'),
    
    # 资产维修管理路由
    path('asset_repair/', admin_office_views.AssetRepairListView.as_view(), name='asset_repair_list'),
    path('asset_repair/create/', admin_office_views.AssetRepairCreateView.as_view(), name='asset_repair_create'),
    path('asset_repair/update/<int:pk>/', admin_office_views.AssetRepairUpdateView.as_view(), name='asset_repair_update'),
    path('asset_repair/delete/<int:pk>/', admin_office_views.AssetRepairDeleteView.as_view(), name='asset_repair_delete'),
    path('asset_repair/complete/<int:pk>/', admin_office_views.AssetRepairCompleteView.as_view(), name='asset_repair_complete'),
    
    # 车辆管理路由
    path('vehicle/', admin_office_views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicle/create/', admin_office_views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicle/update/<int:pk>/', admin_office_views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('vehicle/delete/<int:pk>/', admin_office_views.VehicleDeleteView.as_view(), name='vehicle_delete'),
    
    # 车辆维护管理路由
    path('vehicle_maintenance/', admin_office_views.VehicleMaintenanceListView.as_view(), name='vehicle_maintenance_list'),
    path('vehicle_maintenance/create/', admin_office_views.VehicleMaintenanceCreateView.as_view(), name='vehicle_maintenance_create'),
    path('vehicle_maintenance/update/<int:pk>/', admin_office_views.VehicleMaintenanceUpdateView.as_view(), name='vehicle_maintenance_update'),
    path('vehicle_maintenance/delete/<int:pk>/', admin_office_views.VehicleMaintenanceDeleteView.as_view(), name='vehicle_maintenance_delete'),
    
    # 车辆费用管理路由
    path('vehicle_fee/', admin_office_views.VehicleFeeListView.as_view(), name='vehicle_fee_list'),
    path('vehicle_fee/create/', admin_office_views.VehicleFeeCreateView.as_view(), name='vehicle_fee_create'),
    path('vehicle_fee/update/<int:pk>/', admin_office_views.VehicleFeeUpdateView.as_view(), name='vehicle_fee_update'),
    path('vehicle_fee/delete/<int:pk>/', admin_office_views.VehicleFeeDeleteView.as_view(), name='vehicle_fee_delete'),
    
    # 车辆加油管理路由
    path('vehicle_oil/', admin_office_views.VehicleOilListView.as_view(), name='vehicle_oil_list'),
    path('vehicle_oil/create/', admin_office_views.VehicleOilCreateView.as_view(), name='vehicle_oil_create'),
    path('vehicle_oil/update/<int:pk>/', admin_office_views.VehicleOilUpdateView.as_view(), name='vehicle_oil_update'),
    path('vehicle_oil/delete/<int:pk>/', admin_office_views.VehicleOilDeleteView.as_view(), name='vehicle_oil_delete'),
]