"""
行政办公视图模块
包含公告管理、会议室管理、印章管理、公文管理、资产管理、车辆管理等视图函数
"""

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.db import transaction

from apps.system.models import (
    Notice, MeetingRoom, MeetingReservation, Seal, SealApplication,
    Document, DocumentCategory, DocumentReview, Asset, AssetRepair,
    Vehicle, VehicleMaintenance, VehicleFee, VehicleOil
)


class NoticeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """公告列表视图"""
    model = Notice
    template_name = 'notice/list.html'
    context_object_name = 'notices'
    paginate_by = 20
    permission_required = 'user.view_notice'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_published=True)
        return queryset.order_by('-is_top', '-publish_time')


class NoticeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """创建公告视图"""
    model = Notice
    template_name = 'notice/form.html'
    fields = ['title', 'content', 'notice_type', 'is_top', 'is_published']
    success_url = reverse_lazy('system:admin_office:notice_list')
    permission_required = 'user.add_notice'
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, '公告创建成功')
        return super().form_valid(form)


class NoticeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """更新公告视图"""
    model = Notice
    template_name = 'notice/form.html'
    fields = ['title', 'content', 'notice_type', 'is_top', 'is_published']
    success_url = reverse_lazy('system:admin_office:notice_list')
    permission_required = 'user.change_notice'
    
    def form_valid(self, form):
        messages.success(self.request, '公告更新成功')
        return super().form_valid(form)


class NoticeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """删除公告视图"""
    model = Notice
    template_name = 'notice/form.html'
    success_url = reverse_lazy('system:admin_office:notice_list')
    permission_required = 'user.delete_notice'
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '公告删除成功')
        return super().delete(request, *args, **kwargs)


class NoticeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """公告详情视图"""
    model = Notice
    template_name = 'notice/detail.html'
    context_object_name = 'notice'
    permission_required = 'user.view_notice'


class NoticePublishView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """发布公告视图"""
    model = Notice
    fields = []
    permission_required = 'user.change_notice'
    
    def post(self, request, *args, **kwargs):
        notice = self.get_object()
        notice.is_published = True
        notice.save()
        messages.success(request, '公告发布成功')
        return redirect('system:admin_office:notice_list')


class MeetingRoomListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """会议室列表视图"""
    model = MeetingRoom
    template_name = 'meeting/room_list.html'
    context_object_name = 'meeting_rooms'
    paginate_by = 20
    permission_required = 'user.view_meeting_room'


class MeetingRoomCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """创建会议室视图"""
    model = MeetingRoom
    template_name = 'meeting/room_form.html'
    fields = ['name', 'capacity', 'location', 'equipment', 'description']
    success_url = reverse_lazy('system:admin_office:meeting_room_list')
    permission_required = 'user.add_meeting_room'
    
    def form_valid(self, form):
        messages.success(self.request, '会议室创建成功')
        return super().form_valid(form)


class MeetingRoomUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """更新会议室视图"""
    model = MeetingRoom
    template_name = 'meeting_room/form.html'
    fields = ['name', 'capacity', 'location', 'equipment', 'description']
    success_url = reverse_lazy('system:admin_office:meeting_room_list')
    permission_required = 'user.change_meeting_room'
    
    def form_valid(self, form):
        messages.success(self.request, '会议室更新成功')
        return super().form_valid(form)


class MeetingRoomDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """删除会议室视图"""
    model = MeetingRoom
    template_name = 'meeting/room_form.html'
    success_url = reverse_lazy('system:admin_office:meeting_room_list')
    permission_required = 'user.delete_meeting_room'
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '会议室删除成功')
        return super().delete(request, *args, **kwargs)


class MeetingReservationListView(LoginRequiredMixin, ListView):
    """会议室预订列表视图"""
    model = MeetingReservation
    template_name = 'meeting/reservation_list.html'
    context_object_name = 'page_obj'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 普通用户只能看到自己的预订
        if not self.request.user.is_superuser:
            queryset = queryset.filter(organizer=self.request.user)
        return queryset.order_by('-start_time', '-created_at')


class MeetingReservationCreateView(LoginRequiredMixin, CreateView):
    """创建会议室预订视图"""
    model = MeetingReservation
    template_name = 'system/meeting/reservation_form.html'
    fields = ['meeting_room', 'reservation_time', 'end_time', 'participants', 'purpose', 'remarks']
    success_url = reverse_lazy('system:admin_office:meeting_reservation_list')
    
    def form_valid(self, form):
        form.instance.applicant = self.request.user
        messages.success(self.request, '会议室预订申请已提交')
        return super().form_valid(form)


class MeetingReservationUpdateView(LoginRequiredMixin, UpdateView):
    """更新会议室预订视图"""
    model = MeetingReservation
    template_name = 'system/meeting/reservation_form.html'
    fields = ['meeting_room', 'reservation_time', 'end_time', 'participants', 'purpose', 'remarks']
    success_url = reverse_lazy('system:admin_office:meeting_reservation_list')
    
    def form_valid(self, form):
        messages.success(self.request, '会议室预订更新成功')
        return super().form_valid(form)


class MeetingReservationDeleteView(LoginRequiredMixin, DeleteView):
    """删除会议室预订视图"""
    model = MeetingReservation
    template_name = 'system/meeting/reservation_list.html'
    success_url = reverse_lazy('system:admin_office:meeting_reservation_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '会议室预订删除成功')
        return super().delete(request, *args, **kwargs)


class MeetingReservationApproveView(LoginRequiredMixin, UpdateView):
    """审批会议室预订视图"""
    model = MeetingReservation
    fields = []
    
    def post(self, request, *args, **kwargs):
        reservation = self.get_object()
        reservation.status = 'approved'
        reservation.approver = request.user
        reservation.save()
        messages.success(request, '会议室预订已批准')
        return redirect('system:admin_office:meeting_reservation_list')


class MeetingReservationRejectView(LoginRequiredMixin, UpdateView):
    """拒绝会议室预订视图"""
    model = MeetingReservation
    fields = []
    
    def post(self, request, *args, **kwargs):
        reservation = self.get_object()
        reservation.status = 'rejected'
        reservation.approver = request.user
        reservation.save()
        messages.success(request, '会议室预订已拒绝')
        return redirect('system:admin_office:meeting_reservation_list')


class SealListView(LoginRequiredMixin, ListView):
    """印章列表视图"""
    model = Seal
    template_name = 'seal/list.html'
    context_object_name = 'seals'
    paginate_by = 20


class SealCreateView(LoginRequiredMixin, CreateView):
    """创建印章视图"""
    model = Seal
    template_name = 'seal/form.html'
    fields = ['name', 'type', 'keeper', 'status', 'description']
    success_url = reverse_lazy('system:admin_office:seal_list')
    
    def form_valid(self, form):
        messages.success(self.request, '印章创建成功')
        return super().form_valid(form)


class SealUpdateView(LoginRequiredMixin, UpdateView):
    """更新印章视图"""
    model = Seal
    template_name = 'seal/form.html'
    fields = ['name', 'type', 'keeper', 'status', 'description']
    success_url = reverse_lazy('system:admin_office:seal_list')
    
    def form_valid(self, form):
        messages.success(self.request, '印章更新成功')
        return super().form_valid(form)


class SealDeleteView(LoginRequiredMixin, DeleteView):
    """删除印章视图"""
    model = Seal
    template_name = 'seal/list.html'
    success_url = reverse_lazy('system:admin_office:seal_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '印章删除成功')
        return super().delete(request, *args, **kwargs)


class SealApplicationListView(LoginRequiredMixin, ListView):
    """印章申请列表视图"""
    model = SealApplication
    template_name = 'seal/application_list.html'
    context_object_name = 'applications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 普通用户只能看到自己的申请
        if not self.request.user.is_superuser:
            queryset = queryset.filter(applicant=self.request.user)
        return queryset.order_by('-created_at')


class SealApplicationCreateView(LoginRequiredMixin, CreateView):
    """创建印章申请视图"""
    model = SealApplication
    template_name = 'seal/application_form.html'
    fields = ['seal', 'purpose', 'document_title', 'use_date', 'copies']
    success_url = reverse_lazy('system:admin_office:seal_application_list')
    
    def form_valid(self, form):
        form.instance.applicant = self.request.user
        messages.success(self.request, '印章申请已提交')
        return super().form_valid(form)


class SealApplicationUpdateView(LoginRequiredMixin, UpdateView):
    """更新印章申请视图"""
    model = SealApplication
    template_name = 'seal/application_form.html'
    fields = ['seal', 'purpose', 'document_title', 'use_date', 'copies']
    success_url = reverse_lazy('system:admin_office:seal_application_list')
    
    def form_valid(self, form):
        messages.success(self.request, '印章申请更新成功')
        return super().form_valid(form)


class SealApplicationDeleteView(LoginRequiredMixin, DeleteView):
    """删除印章申请视图"""
    model = SealApplication
    template_name = 'seal/application_list.html'
    success_url = reverse_lazy('system:admin_office:seal_application_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '印章申请删除成功')
        return super().delete(request, *args, **kwargs)


class SealApplicationApproveView(LoginRequiredMixin, UpdateView):
    """审批印章申请视图"""
    model = SealApplication
    fields = []
    
    def post(self, request, *args, **kwargs):
        application = self.get_object()
        application.status = 'approved'
        application.approver = request.user
        application.save()
        messages.success(request, '印章申请已批准')
        return redirect('system:admin_office:seal_application_list')


class SealApplicationRejectView(LoginRequiredMixin, UpdateView):
    """拒绝印章申请视图"""
    model = SealApplication
    fields = []
    
    def post(self, request, *args, **kwargs):
        application = self.get_object()
        application.status = 'rejected'
        application.approver = request.user
        application.save()
        messages.success(request, '印章申请已拒绝')
        return redirect('system:admin_office:seal_application_list')


class DocumentListView(LoginRequiredMixin, ListView):
    """公文列表视图"""
    model = Document
    template_name = 'document/list.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 根据权限过滤数据
        if not self.request.user.is_superuser:
            queryset = queryset.filter(status='published')
        return queryset.order_by('-created_at')


class DocumentCreateView(LoginRequiredMixin, CreateView):
    """创建公文视图"""
    model = Document
    template_name = 'document/form.html'
    fields = ['title', 'category', 'content', 'urgency', 'security_level', 'attachments']
    success_url = reverse_lazy('system:admin_office:document_list')
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, '公文创建成功')
        return super().form_valid(form)


class DocumentUpdateView(LoginRequiredMixin, UpdateView):
    """更新公文视图"""
    model = Document
    template_name = 'document/form.html'
    fields = ['title', 'category', 'content', 'urgency', 'security_level', 'attachments']
    success_url = reverse_lazy('system:admin_office:document_list')
    
    def form_valid(self, form):
        messages.success(self.request, '公文更新成功')
        return super().form_valid(form)


class DocumentDeleteView(LoginRequiredMixin, DeleteView):
    """删除公文视图"""
    model = Document
    template_name = 'document/list.html'
    success_url = reverse_lazy('system:admin_office:document_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '公文删除成功')
        return super().delete(request, *args, **kwargs)


class DocumentDetailView(LoginRequiredMixin, DetailView):
    """公文详情视图"""
    model = Document
    template_name = 'document/detail.html'
    context_object_name = 'document'


class DocumentSubmitView(LoginRequiredMixin, UpdateView):
    """提交公文视图"""
    model = Document
    fields = []
    
    def post(self, request, *args, **kwargs):
        document = self.get_object()
        document.status = 'submitted'
        document.save()
        messages.success(request, '公文已提交审核')
        return redirect('system:admin_office:document_list')


class DocumentApproveView(LoginRequiredMixin, UpdateView):
    """审批公文视图"""
    model = Document
    fields = []
    
    def post(self, request, *args, **kwargs):
        document = self.get_object()
        document.status = 'approved'
        document.approver = request.user
        document.save()
        messages.success(request, '公文已批准')
        return redirect('system:admin_office:document_list')


class DocumentRejectView(LoginRequiredMixin, UpdateView):
    """拒绝公文视图"""
    model = Document
    fields = []
    
    def post(self, request, *args, **kwargs):
        document = self.get_object()
        document.status = 'rejected'
        document.approver = request.user
        document.save()
        messages.success(request, '公文已拒绝')
        return redirect('system:admin_office:document_list')


class DocumentPublishView(LoginRequiredMixin, UpdateView):
    """发布公文视图"""
    model = Document
    fields = []
    
    def post(self, request, *args, **kwargs):
        document = self.get_object()
        document.status = 'published'
        document.save()
        messages.success(request, '公文已发布')
        return redirect('system:admin_office:document_list')


class DocumentCategoryListView(LoginRequiredMixin, ListView):
    """公文分类列表视图"""
    model = DocumentCategory
    template_name = 'document/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20


class DocumentCategoryCreateView(LoginRequiredMixin, CreateView):
    """创建公文分类视图"""
    model = DocumentCategory
    template_name = 'document/category_list.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('system:admin_office:document_category_list')
    
    def form_valid(self, form):
        messages.success(self.request, '公文分类创建成功')
        return super().form_valid(form)


class DocumentCategoryUpdateView(LoginRequiredMixin, UpdateView):
    """更新公文分类视图"""
    model = DocumentCategory
    template_name = 'document/category_list.html'
    fields = ['name', 'description', 'parent']
    success_url = reverse_lazy('system:admin_office:document_category_list')
    
    def form_valid(self, form):
        messages.success(self.request, '公文分类更新成功')
        return super().form_valid(form)


class DocumentCategoryDeleteView(LoginRequiredMixin, DeleteView):
    """删除公文分类视图"""
    model = DocumentCategory
    template_name = 'document/category_list.html'
    success_url = reverse_lazy('system:admin_office:document_category_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '公文分类删除成功')
        return super().delete(request, *args, **kwargs)


class AssetListView(LoginRequiredMixin, ListView):
    """资产列表视图"""
    model = Asset
    template_name = 'asset/list.html'
    context_object_name = 'assets'
    paginate_by = 20


class AssetCreateView(LoginRequiredMixin, CreateView):
    """创建资产视图"""
    model = Asset
    template_name = 'asset/form.html'
    fields = ['name', 'code', 'category', 'model', 'specification', 'purchase_date', 'purchase_price', 'status', 'location', 'responsible_person', 'description']
    success_url = reverse_lazy('system:admin_office:asset_list')
    
    def form_valid(self, form):
        messages.success(self.request, '资产创建成功')
        return super().form_valid(form)


class AssetUpdateView(LoginRequiredMixin, UpdateView):
    """更新资产视图"""
    model = Asset
    template_name = 'asset/form.html'
    fields = ['name', 'code', 'category', 'model', 'specification', 'purchase_date', 'purchase_price', 'status', 'location', 'responsible_person', 'description']
    success_url = reverse_lazy('system:admin_office:asset_list')
    
    def form_valid(self, form):
        messages.success(self.request, '资产更新成功')
        return super().form_valid(form)





class AssetDeleteView(LoginRequiredMixin, DeleteView):
    """删除资产视图"""
    model = Asset
    template_name = 'asset/list.html'
    success_url = reverse_lazy('system:admin_office:asset_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '资产删除成功')
        return super().delete(request, *args, **kwargs)


class AssetRepairListView(LoginRequiredMixin, ListView):
    """资产维修记录列表视图"""
    model = AssetRepair
    template_name = 'asset/repair_list.html'
    context_object_name = 'repairs'
    paginate_by = 20


class AssetRepairCreateView(LoginRequiredMixin, CreateView):
    """创建资产维修记录视图"""
    model = AssetRepair
    template_name = 'asset/repair_form.html'
    fields = ['asset', 'fault_description', 'repair_cost']
    success_url = reverse_lazy('system:admin_office:asset_repair_list')
    
    def form_valid(self, form):
        form.instance.reporter = self.request.user
        messages.success(self.request, '资产维修申请已提交')
        return super().form_valid(form)


class AssetRepairUpdateView(LoginRequiredMixin, UpdateView):
    """更新资产维修记录视图"""
    model = AssetRepair
    template_name = 'asset/repair_form.html'
    fields = ['asset', 'fault_description', 'repair_cost', 'status']
    success_url = reverse_lazy('system:admin_office:asset_repair_list')
    
    def form_valid(self, form):
        messages.success(self.request, '资产维修记录更新成功')
        return super().form_valid(form)





class AssetRepairDeleteView(LoginRequiredMixin, DeleteView):
    """删除资产维修记录视图"""
    model = AssetRepair
    template_name = 'asset/repair_list.html'
    success_url = reverse_lazy('system:admin_office:asset_repair_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '资产维修删除成功')
        return super().delete(request, *args, **kwargs)


class AssetRepairCompleteView(LoginRequiredMixin, UpdateView):
    """完成资产维修视图"""
    model = AssetRepair
    fields = []
    
    def post(self, request, *args, **kwargs):
        repair = self.get_object()
        repair.status = 'completed'
        repair.save()
        messages.success(request, '资产维修已完成')
        return redirect('system:admin_office:asset_repair_list')


class VehicleListView(LoginRequiredMixin, ListView):
    """车辆列表视图"""
    model = Vehicle
    template_name = 'vehicle/list.html'
    context_object_name = 'vehicles'
    paginate_by = 20


class VehicleCreateView(LoginRequiredMixin, CreateView):
    """创建车辆视图"""
    model = Vehicle
    template_name = 'vehicle/form.html'
    fields = ['license_plate', 'brand', 'model', 'color', 'purchase_date', 
              'purchase_price', 'status', 'driver', 'description']
    success_url = reverse_lazy('system:admin_office:vehicle_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆创建成功')
        return super().form_valid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    """更新车辆视图"""
    model = Vehicle
    template_name = 'vehicle/form.html'
    fields = ['license_plate', 'brand', 'model', 'color', 'purchase_date', 
              'purchase_price', 'status', 'driver', 'description']
    success_url = reverse_lazy('system:admin_office:vehicle_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆更新成功')
        return super().form_valid(form)


class VehicleDeleteView(LoginRequiredMixin, DeleteView):
    """删除车辆视图"""
    model = Vehicle
    template_name = 'vehicle/list.html'
    success_url = reverse_lazy('system:admin_office:vehicle_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '车辆删除成功')
        return super().delete(request, *args, **kwargs)


class VehicleMaintenanceListView(LoginRequiredMixin, ListView):
    """车辆保养记录列表视图"""
    model = VehicleMaintenance
    template_name = 'vehicle/maintenance_list.html'
    context_object_name = 'maintenances'
    paginate_by = 20


class VehicleMaintenanceCreateView(LoginRequiredMixin, CreateView):
    """创建车辆保养记录视图"""
    model = VehicleMaintenance
    template_name = 'vehicle/maintenance_form.html'
    fields = ['vehicle', 'maintenance_date', 'maintenance_type', 'cost', 'description']
    success_url = reverse_lazy('system:admin_office:vehicle_maintenance_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆保养记录创建成功')
        return super().form_valid(form)


class VehicleMaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    """更新车辆保养记录视图"""
    model = VehicleMaintenance
    template_name = 'vehicle/maintenance_form.html'
    fields = ['vehicle', 'maintenance_date', 'maintenance_type', 'cost', 'description']
    success_url = reverse_lazy('system:admin_office:vehicle_maintenance_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆保养记录更新成功')
        return super().form_valid(form)


class VehicleMaintenanceDeleteView(LoginRequiredMixin, DeleteView):
    """删除车辆保养记录视图"""
    model = VehicleMaintenance
    template_name = 'vehicle/maintenance_list.html'
    success_url = reverse_lazy('system:admin_office:vehicle_maintenance_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '车辆保养记录删除成功')
        return super().delete(request, *args, **kwargs)


class VehicleFeeListView(LoginRequiredMixin, ListView):
    """车辆费用记录列表视图"""
    model = VehicleFee
    template_name = 'vehicle/fee_list.html'
    context_object_name = 'fees'
    paginate_by = 20


class VehicleFeeCreateView(LoginRequiredMixin, CreateView):
    """创建车辆费用视图"""
    model = VehicleFee
    template_name = 'vehicle/fee_form.html'
    fields = ['vehicle', 'fee_date', 'fee_type', 'fee_amount', 'payment_method', 'remarks']
    success_url = reverse_lazy('system:admin_office:vehicle_fee_list')
    
    def form_valid(self, form):
        form.instance.recorder = self.request.user
        messages.success(self.request, '车辆费用记录已创建')
        return super().form_valid(form)


class VehicleFeeUpdateView(LoginRequiredMixin, UpdateView):
    """更新车辆费用视图"""
    model = VehicleFee
    template_name = 'vehicle/fee_form.html'
    fields = ['vehicle', 'fee_date', 'fee_type', 'fee_amount', 'payment_method', 'remarks']
    success_url = reverse_lazy('system:admin_office:vehicle_fee_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆费用记录更新成功')
        return super().form_valid(form)


class VehicleFeeDeleteView(LoginRequiredMixin, DeleteView):
    """删除车辆费用视图"""
    model = VehicleFee
    template_name = 'vehicle/fee_list.html'
    success_url = reverse_lazy('system:admin_office:vehicle_fee_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '车辆费用记录删除成功')
        return super().delete(request, *args, **kwargs)


class VehicleOilListView(LoginRequiredMixin, ListView):
    """车辆加油记录列表视图"""
    model = VehicleOil
    template_name = 'vehicle/oil_list.html'
    context_object_name = 'oils'
    paginate_by = 20


class VehicleOilCreateView(LoginRequiredMixin, CreateView):
    """创建车辆加油记录视图"""
    model = VehicleOil
    template_name = 'vehicle/oil_form.html'
    fields = ['vehicle', 'oil_date', 'oil_type', 'oil_amount', 'oil_cost', 'current_mileage', 'remarks']
    success_url = reverse_lazy('system:admin_office:vehicle_oil_list')
    
    def form_valid(self, form):
        form.instance.recorder = self.request.user
        messages.success(self.request, '车辆加油记录已创建')
        return super().form_valid(form)


class VehicleOilUpdateView(LoginRequiredMixin, UpdateView):
    """更新车辆加油记录视图"""
    model = VehicleOil
    template_name = 'vehicle/oil_form.html'
    fields = ['vehicle', 'oil_date', 'oil_type', 'oil_amount', 'oil_cost', 'description']
    success_url = reverse_lazy('system:admin_office:vehicle_oil_list')
    
    def form_valid(self, form):
        messages.success(self.request, '车辆加油记录更新成功')
        return super().form_valid(form)


class VehicleOilDeleteView(LoginRequiredMixin, DeleteView):
    """删除车辆加油记录视图"""
    model = VehicleOil
    template_name = 'vehicle/oil_list.html'
    success_url = reverse_lazy('system:admin_office:vehicle_oil_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '车辆加油记录删除成功')
        return super().delete(request, *args, **kwargs)