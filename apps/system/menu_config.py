#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统菜单配置文件
此文件包含系统所有菜单的配置信息，如果修改这个文件，必须同步修改数据库菜单数据，需要始终保持菜单数据一致。
"""

# 系统菜单配置
system_menus = {
    1: {
        "id": 1,
        "title": "收藏文件",
        "src": "/adm/disk/starred/",
        "pid_id": 1274,
        "sort": 138,
        "status": 1
    },
    2: {
        "id": 2,
        "title": "知识库管理",
        "src": "/ai/knowledge-base/list/",
        "pid_id": 1271,
        "sort": 130,
        "status": 1
    },
    1095: {
        "id": 1095,
        "title": "工作台",
        "src": "/dashboard/",
        "pid_id": 0,
        "sort": 1,
        "status": 1
    },
    1096: {
        "id": 1096,
        "title": "系统管理",
        "src": "javascript:;",
        "pid_id": 0,
        "sort": 2,
        "status": 1
    },
    1097: {
        "id": 1097,
        "title": "系统配置",
        "src": "/system/config/",
        "pid_id": 1096,
        "sort": 3,
        "status": 1
    },
    1098: {
        "id": 1098,
        "title": "功能模块",
        "src": "/system/module/",
        "pid_id": 1096,
        "sort": 4,
        "status": 1
    },
    1101: {
        "id": 1101,
        "title": "操作日志",
        "src": "/system/log/",
        "pid_id": 1096,
        "sort": 6,
        "status": 1
    },
    1102: {
        "id": 1102,
        "title": "菜单管理",
        "src": "/system/menu/",
        "pid_id": 1096,
        "sort": 5,
        "status": 1
    },
    1103: {
        "id": 1103,
        "title": "附件管理",
        "src": "/system/attachment/",
        "pid_id": 1096,
        "sort": 7,
        "status": 1
    },
    1104: {
        "id": 1104,
        "title": "备份数据",
        "src": "/system/backup/",
        "pid_id": 1096,
        "sort": 8,
        "status": 1
    },
    1107: {
        "id": 1107,
        "title": "人事管理",
        "src": "javascript:;",
        "pid_id": 0,
        "sort": 9,
        "status": 1
    },
    1108: {
        "id": 1108,
        "title": "部门管理",
        "src": "/system/department/",
        "pid_id": 1107,
        "sort": 10,
        "status": 1
    },
    1109: {
        "id": 1109,
        "title": "岗位职称",
        "src": "/position/",
        "pid_id": 1107,
        "sort": 11,
        "status": 1
    },
    1405: {
        "id": 1405,
        "title": "角色管理",
        "src": "/user/group/",
        "pid_id": 1107,
        "sort": 12,
        "status": 1
    },
    1114: {
        "id": 1114,
        "title": "奖罚管理",
        "src": "/user/reward-punishment/",
        "pid_id": 1107,
        "sort": 14,
        "status": 1
    },
    1115: {
        "id": 1115,
        "title": "员工关怀",
        "src": "/user/employee-care/",
        "pid_id": 1107,
        "sort": 15,
        "status": 1
    },

    1122: {
        "id": 1122,
        "title": "行政办公",
        "src": "/system/admin_office/notice/",
        "pid_id": 0,
        "sort": 16,
        "status": 1
    },
    1123: {
        "id": 1123,
        "title": "固定资产",
        "src": "/oa/assets/",
        "pid_id": 1122,
        "sort": 17,
        "status": 1
    },
    1126: {
        "id": 1126,
        "title": "资产归还",
        "src": "/oa/assets/return/",
        "pid_id": 1123,
        "sort": 19,
        "status": 1
    },
    1127: {
        "id": 1127,
        "title": "资产维修",
        "src": "/oa/assets/repair/",
        "pid_id": 1123,
        "sort": 20,
        "status": 1
    },
    1128: {
        "id": 1128,
        "title": "资产报废",
        "src": "/oa/assets/scrap/",
        "pid_id": 1123,
        "sort": 21,
        "status": 1
    },
    1129: {
        "id": 1129,
        "title": "车辆管理",
        "src": "/oa/vehicle/",
        "pid_id": 1122,
        "sort": 22,
        "status": 1
    },
    1130: {
        "id": 1130,
        "title": "车辆信息",
        "src": "/oa/vehicle/info/",
        "pid_id": 1129,
        "sort": 23,
        "status": 1
    },
    1131: {
        "id": 1131,
        "title": "用车申请",
        "src": "/oa/vehicle/apply/",
        "pid_id": 1129,
        "sort": 24,
        "status": 1
    },
    1132: {
        "id": 1132,
        "title": "车辆维修",
        "src": "/oa/vehicle/maintain/",
        "pid_id": 1129,
        "sort": 25,
        "status": 1
    },
    1133: {
        "id": 1133,
        "title": "车辆调度",
        "src": "/oa/vehicle/dispatch/",
        "pid_id": 1129,
        "sort": 26,
        "status": 1
    },
    1134: {
        "id": 1134,
        "title": "车辆保养",
        "src": "/oa/vehicle/maintain/",
        "pid_id": 1129,
        "sort": 27,
        "status": 1
    },
    1135: {
        "id": 1135,
        "title": "车辆费用",
        "src": "/oa/vehicle/",
        "pid_id": 1129,
        "sort": 28,
        "status": 1
    },
    1136: {
        "id": 1136,
        "title": "车辆油耗",
        "src": "/oa/vehicle/",
        "pid_id": 1129,
        "sort": 29,
        "status": 1
    },
    1137: {
        "id": 1137,
        "title": "会议管理",
        "src": "/oa/meeting/",
        "pid_id": 1122,
        "sort": 30,
        "status": 1
    },
    1139: {
        "id": 1139,
        "title": "会议纪要",
        "src": "/oa/meeting/minutes/",
        "pid_id": 1137,
        "sort": 33,
        "status": 1
    },
    1140: {
        "id": 1140,
        "title": "会议室管理",
        "src": "/system/admin_office/meeting_room/",
        "pid_id": 1137,
        "sort": 31,
        "status": 1
    },
    1141: {
        "id": 1141,
        "title": "会议记录",
        "src": "/oa/meeting/",
        "pid_id": 1137,
        "sort": 32,
        "status": 1
    },
    1142: {
        "id": 1142,
        "title": "公文管理",
        "src": "/oa/document/",
        "pid_id": 1122,
        "sort": 34,
        "status": 1
    },
    1143: {
        "id": 1143,
        "title": "公文起草",
        "src": "/oa/document/draft/",
        "pid_id": 1142,
        "sort": 35,
        "status": 1
    },
    1144: {
        "id": 1144,
        "title": "公文审核",
        "src": "/oa/document/check/",
        "pid_id": 1142,
        "sort": 36,
        "status": 1
    },
    1145: {
        "id": 1145,
        "title": "公文发布",
        "src": "/oa/document/publish/",
        "pid_id": 1142,
        "sort": 37,
        "status": 1
    },
    1146: {
        "id": 1146,
        "title": "公文查看",
        "src": "/oa/document/view/",
        "pid_id": 1142,
        "sort": 38,
        "status": 1
    },
    1147: {
        "id": 1147,
        "title": "公文分类",
        "src": "/oa/document/",
        "pid_id": 1142,
        "sort": 39,
        "status": 1
    },
    1150: {
        "id": 1150,
        "title": "用章管理",
        "src": "/oa/seal/",
        "pid_id": 1122,
        "sort": 42,
        "status": 1
    },
    1151: {
        "id": 1151,
        "title": "印章管理",
        "src": "/oa/seal/manage/",
        "pid_id": 1150,
        "sort": 43,
        "status": 1
    },
    1152: {
        "id": 1152,
        "title": "用章申请",
        "src": "/oa/seal/apply/",
        "pid_id": 1150,
        "sort": 44,
        "status": 1
    },
    1153: {
        "id": 1153,
        "title": "用章记录",
        "src": "/oa/seal/record/",
        "pid_id": 1150,
        "sort": 45,
        "status": 1
    },
    1154: {
        "id": 1154,
        "title": "公告列表",
        "src": "/system/admin_office/notice/",
        "pid_id": 1122,
        "sort": 46,
        "status": 1
    },
    1156: {
        "id": 1156,
        "title": "资产分类",
        "src": "/system/admin_office/asset/",
        "pid_id": 1122,
        "sort": 48,
        "status": 1
    },
    1157: {
        "id": 1157,
        "title": "资产品牌",
        "src": "/system/admin_office/asset/",
        "pid_id": 1122,
        "sort": 49,
        "status": 1
    },
    1161: {
        "id": 1161,
        "title": "通知类型",
        "src": "/system/admin_office/notice/",
        "pid_id": 1122,
        "sort": 50,
        "status": 1
    },
    1162: {
        "id": 1162,
        "title": "个人办公",
        "src": "/personal/schedule/",
        "pid_id": 0,
        "sort": 51,
        "status": 1
    },
    1167: {
        "id": 1167,
        "title": "日程安排",
        "src": "/personal/schedule/",
        "pid_id": 1162,
        "sort": 52,
        "status": 1
    },
    1169: {
        "id": 1169,
        "title": "工作日历",
        "src": "/personal/schedule/",
        "pid_id": 1162,
        "sort": 53,
        "status": 1
    },
    1170: {
        "id": 1170,
        "title": "工作汇报",
        "src": "/personal/report/",
        "pid_id": 1162,
        "sort": 54,
        "status": 1
    },
    1172: {
        "id": 1172,
        "title": "财务管理",
        "src": "/finance/",
        "pid_id": 0,
        "sort": 55,
        "status": 1
    },
    1173: {
        "id": 1173,
        "title": "报销管理",
        "src": "/finance/reimbursement/",
        "pid_id": 1172,
        "sort": 56,
        "status": 1
    },
    1175: {
        "id": 1175,
        "title": "开票管理",
        "src": "/finance/invoice/",
        "pid_id": 1172,
        "sort": 57,
        "status": 1
    },
    1176: {
        "id": 1176,
        "title": "收票管理",
        "src": "/finance/receive_invoice/",
        "pid_id": 1172,
        "sort": 58,
        "status": 1
    },
    1177: {
        "id": 1177,
        "title": "回款管理",
        "src": "/finance/receivable/",
        "pid_id": 1172,
        "sort": 59,
        "status": 1
    },
    1178: {
        "id": 1178,
        "title": "付款管理",
        "src": "/finance/payable/",
        "pid_id": 1172,
        "sort": 60,
        "status": 1
    },
    1179: {
        "id": 1179,
        "title": "报销类型",
        "src": "/finance/expense/",
        "pid_id": 1172,
        "sort": 61,
        "status": 1
    },
    1180: {
        "id": 1180,
        "title": "费用类型",
        "src": "/finance/expense/",
        "pid_id": 1172,
        "sort": 62,
        "status": 1
    },
    1181: {
        "id": 1181,
        "title": "财务统计",
        "src": "/finance/stat/",
        "pid_id": 1172,
        "sort": 63,
        "status": 1
    },
    1182: {
        "id": 1182,
        "title": "报销记录",
        "src": "/adm/finance/statistics/reimbursement/",
        "pid_id": 1181,
        "sort": 64,
        "status": 1
    },
    1183: {
        "id": 1183,
        "title": "开票记录",
        "src": "/adm/finance/statistics/invoice/",
        "pid_id": 1181,
        "sort": 65,
        "status": 1
    },
    1184: {
        "id": 1184,
        "title": "收票记录",
        "src": "/adm/finance/statistics/receiveinvoice/",
        "pid_id": 1181,
        "sort": 66,
        "status": 1
    },
    1185: {
        "id": 1185,
        "title": "回款记录",
        "src": "/adm/finance/statistics/paymentreceive/",
        "pid_id": 1181,
        "sort": 67,
        "status": 1
    },
    1186: {
        "id": 1186,
        "title": "付款记录",
        "src": "/adm/finance/statistics/payment/",
        "pid_id": 1181,
        "sort": 68,
        "status": 1
    },
    1187: {
        "id": 1187,
        "title": "客户管理",
        "src": "/customer/",
        "pid_id": 0,
        "sort": 69,
        "status": 1
    },
    1188: {
        "id": 1188,
        "title": "客户列表",
        "src": "/customer/list/",
        "pid_id": 1187,
        "sort": 70,
        "status": 1
    },
    1189: {
        "id": 1189,
        "title": "客户公海",
        "src": "/customer/public/list/",
        "pid_id": 1187,
        "sort": 71,
        "status": 1
    },
    1190: {
        "id": 1190,
        "title": "公海列表",
        "src": "/customer/public/list/",
        "pid_id": 1189,
        "sort": 72,
        "status": 1
    },
    1191: {
        "id": 1191,
        "title": "爬虫任务",
        "src": "/adm/customer/spider_task/",
        "pid_id": 1189,
        "sort": 73,
        "status": 1
    },
    1192: {
        "id": 1192,
        "title": "AI机器人",
        "src": "/customer/public/ai-robot/",
        "pid_id": 1189,
        "sort": 74,
        "status": 1
    },
    1193: {
        "id": 1193,
        "title": "废弃客户",
        "src": "/customer/discard/",
        "pid_id": 1187,
        "sort": 75,
        "status": 1
    },
    1194: {
        "id": 1194,
        "title": "客户订单",
        "src": "/customer/order/",
        "pid_id": 1187,
        "sort": 76,
        "status": 1
    },
    1196: {
        "id": 1196,
        "title": "跟进记录",
        "src": "/adm/customer/followup/",
        "pid_id": 1187,
        "sort": 77,
        "status": 1
    },
    1197: {
        "id": 1197,
        "title": "拨号记录",
        "src": "/adm/customer/callrecord/",
        "pid_id": 1187,
        "sort": 78,
        "status": 1
    },
    1201: {
        "id": 1201,
        "title": "客户字段",
        "src": "/customer/field/list/",
        "pid_id": 1187,
        "sort": 79,
        "status": 1
    },
    1202: {
        "id": 1202,
        "title": "客户来源",
        "src": "/customer/source/list/",
        "pid_id": 1187,
        "sort": 80,
        "status": 1
    },
    1203: {
        "id": 1203,
        "title": "客户等级",
        "src": "/customer/grade/list/",
        "pid_id": 1187,
        "sort": 81,
        "status": 1
    },
    1204: {
        "id": 1204,
        "title": "客户意向",
        "src": "/customer/intent/list/",
        "pid_id": 1187,
        "sort": 82,
        "status": 1
    },
    1205: {
        "id": 1205,
        "title": "跟进字段",
        "src": "/customer/follow/field/list/",
        "pid_id": 1187,
        "sort": 83,
        "status": 1
    },
    1206: {
        "id": 1206,
        "title": "订单字段",
        "src": "/customer/order/field/list/",
        "pid_id": 1187,
        "sort": 84,
        "status": 1
    },
    1207: {
        "id": 1207,
        "title": "合同管理",
        "src": "/contract/",
        "pid_id": 0,
        "sort": 85,
        "status": 1
    },
    1208: {
        "id": 1208,
        "title": "合同列表",
        "src": "/contract/list/",
        "pid_id": 1207,
        "sort": 86,
        "status": 1
    },
    1209: {
        "id": 1209,
        "title": "合同模板",
        "src": "/contract/template/",
        "pid_id": 1207,
        "sort": 87,
        "status": 1
    },
    1210: {
        "id": 1210,
        "title": "合同审核",
        "src": "/contract/audit/",
        "pid_id": 1207,
        "sort": 88,
        "status": 1
    },
    1212: {
        "id": 1212,
        "title": "合同归档",
        "src": "/contract/archive/",
        "pid_id": 1207,
        "sort": 89,
        "status": 1
    },
    1213: {
        "id": 1213,
        "title": "销售合同",
        "src": "/adm/contract/sales/",
        "pid_id": 1207,
        "sort": 90,
        "status": 1
    },
    1214: {
        "id": 1214,
        "title": "采购合同",
        "src": "/adm/contract/purchase/",
        "pid_id": 1207,
        "sort": 91,
        "status": 1
    },
    1215: {
        "id": 1215,
        "title": "中止合同",
        "src": "/adm/contract/terminate/",
        "pid_id": 1207,
        "sort": 92,
        "status": 1
    },
    1216: {
        "id": 1216,
        "title": "作废合同",
        "src": "/adm/contract/cancel/",
        "pid_id": 1207,
        "sort": 93,
        "status": 1
    },
    1217: {
        "id": 1217,
        "title": "合同分类",
        "src": "/contract/category/",
        "pid_id": 1207,
        "sort": 94,
        "status": 1
    },
    1218: {
        "id": 1218,
        "title": "产品分类",
        "src": "/contract/productcategory/",
        "pid_id": 1207,
        "sort": 95,
        "status": 1
    },
    1219: {
        "id": 1219,
        "title": "产品管理",
        "src": "/contract/product/",
        "pid_id": 1207,
        "sort": 96,
        "status": 1
    },
    1220: {
        "id": 1220,
        "title": "服务管理",
        "src": "/contract/servicecategory/",
        "pid_id": 1207,
        "sort": 97,
        "status": 1
    },
    1221: {
        "id": 1221,
        "title": "供应商管理",
        "src": "/contract/supplier/",
        "pid_id": 1207,
        "sort": 98,
        "status": 1
    },
    1222: {
        "id": 1222,
        "title": "采购分类",
        "src": "/contract/purchasecategory/",
        "pid_id": 1207,
        "sort": 99,
        "status": 1
    },
    1223: {
        "id": 1223,
        "title": "采购项目",
        "src": "/contract/purchase/",
        "pid_id": 1207,
        "sort": 100,
        "status": 1
    },
    1224: {
        "id": 1224,
        "title": "项目管理",
        "src": "/project/",
        "pid_id": 0,
        "sort": 101,
        "status": 1
    },
    1225: {
        "id": 1225,
        "title": "项目列表",
        "src": "/project/list/",
        "pid_id": 1224,
        "sort": 102,
        "status": 1
    },
    1226: {
        "id": 1226,
        "title": "项目分类",
        "src": "/project/category/",
        "pid_id": 1224,
        "sort": 103,
        "status": 1
    },
    1227: {
        "id": 1227,
        "title": "任务列表",
        "src": "/project/task/",
        "pid_id": 1224,
        "sort": 104,
        "status": 1
    },
    1228: {
        "id": 1228,
        "title": "工时管理",
        "src": "/task/workhour/",
        "pid_id": 1224,
        "sort": 105,
        "status": 1
    },
    1229: {
        "id": 1229,
        "title": "文档列表",
        "src": "/project/document/",
        "pid_id": 1224,
        "sort": 106,
        "status": 1
    },
    1230: {
        "id": 1230,
        "title": "风险预测",
        "src": "/project/ai/risk-prediction/1/",
        "pid_id": 1224,
        "sort": 107,
        "status": 1
    },
    1231: {
        "id": 1231,
        "title": "进度分析",
        "src": "/project/ai/progress-analysis/1/",
        "pid_id": 1224,
        "sort": 108,
        "status": 1
    },
    1232: {
        "id": 1232,
        "title": "项目阶段",
        "src": "/project/stage/",
        "pid_id": 1224,
        "sort": 109,
        "status": 1
    },
    1233: {
        "id": 1233,
        "title": "项目分类",
        "src": "/project/category/",
        "pid_id": 1224,
        "sort": 110,
        "status": 1
    },
    1234: {
        "id": 1234,
        "title": "工作类型",
        "src": "/project/worktype/",
        "pid_id": 1224,
        "sort": 111,
        "status": 1
    },
    1235: {
        "id": 1235,
        "title": "生产管理",
        "src": "/production/",
        "pid_id": 0,
        "sort": 112,
        "status": 1
    },
    1236: {
        "id": 1236,
        "title": "基础信息",
        "src": "/production/baseinfo/",
        "pid_id": 1235,
        "sort": 113,
        "status": 1
    },
    1237: {
        "id": 1237,
        "title": "基本工序",
        "src": "/production/procedure/",
        "pid_id": 1236,
        "sort": 114,
        "status": 1
    },
    1238: {
        "id": 1238,
        "title": "工序集",
        "src": "/production/procedureset/",
        "pid_id": 1236,
        "sort": 115,
        "status": 1
    },
    1239: {
        "id": 1239,
        "title": "BOM管理",
        "src": "/production/bom/",
        "pid_id": 1236,
        "sort": 116,
        "status": 1
    },
    1240: {
        "id": 1240,
        "title": "设备管理",
        "src": "/production/equipment/",
        "pid_id": 1236,
        "sort": 117,
        "status": 1
    },
    1241: {
        "id": 1241,
        "title": "数据采集",
        "src": "/production/data/",
        "pid_id": 1236,
        "sort": 118,
        "status": 1
    },
    1242: {
        "id": 1242,
        "title": "数据源配置",
        "src": "/production/data/source/",
        "pid_id": 1241,
        "sort": 1181,
        "status": 1
    },
    1243: {
        "id": 1243,
        "title": "数据映射",
        "src": "/production/data/mapping/",
        "pid_id": 1241,
        "sort": 1182,
        "status": 1
    },
    1244: {
        "id": 1244,
        "title": "采集记录",
        "src": "/production/data/record/",
        "pid_id": 1241,
        "sort": 1183,
        "status": 1
    },
    1245: {
        "id": 1245,
        "title": "数据采集任务",
        "src": "/production/data/task/",
        "pid_id": 1241,
        "sort": 1184,
        "status": 1
    },
    1246: {
        "id": 1246,
        "title": "性能分析",
        "src": "/production/analysis/",
        "pid_id": 1236,
        "sort": 119,
        "status": 1
    },
    1247: {
        "id": 1247,
        "title": "SOP管理",
        "src": "/production/sop/",
        "pid_id": 1236,
        "sort": 120,
        "status": 1
    },
    1248: {
        "id": 1248,
        "title": "工艺路线",
        "src": "/production/process/",
        "pid_id": 1236,
        "sort": 122,
        "status": 1
    },
    1249: {
        "id": 1249,
        "title": "物料管理",
        "src": "/production/material/",
        "pid_id": 1235,
        "sort": 1225,
        "status": 1
    },
    1250: {
        "id": 1250,
        "title": "领料申请",
        "src": "/production/material/request/",
        "pid_id": 1249,
        "sort": 1226,
        "status": 1
    },
    1251: {
        "id": 1251,
        "title": "材料出库",
        "src": "/production/material/issue/",
        "pid_id": 1249,
        "sort": 1227,
        "status": 1
    },
    1252: {
        "id": 1252,
        "title": "材料退料",
        "src": "/production/material/return/",
        "pid_id": 1249,
        "sort": 1228,
        "status": 1
    },
    1253: {
        "id": 1253,
        "title": "生产任务",
        "src": "/production/task/",
        "pid_id": 1235,
        "sort": 123,
        "status": 1
    },
    1254: {
        "id": 1254,
        "title": "生产计划",
        "src": "/production/task/plan/",
        "pid_id": 1253,
        "sort": 124,
        "status": 1
    },
    1255: {
        "id": 1255,
        "title": "生产任务",
        "src": "/production/task/execution/",
        "pid_id": 1253,
        "sort": 125,
        "status": 1
    },
    1256: {
        "id": 1256,
        "title": "资源调度",
        "src": "/production/technology/",
        "pid_id": 1253,
        "sort": 126,
        "status": 1
    },
    1257: {
        "id": 1257,
        "title": "生产线日计划",
        "src": "/production/line/dayplan/",
        "pid_id": 1256,
        "sort": 1261,
        "status": 1
    },
    1258: {
        "id": 1258,
        "title": "订单变更",
        "src": "/production/order/change/",
        "pid_id": 1256,
        "sort": 1262,
        "status": 1
    },
    1259: {
        "id": 1259,
        "title": "质量管理",
        "src": "/production/quality/",
        "pid_id": 1253,
        "sort": 127,
        "status": 1
    },
    1260: {
        "id": 1260,
        "title": "设备监控",
        "src": "/production/equipment/monitor/",
        "pid_id": 1253,
        "sort": 128,
        "status": 1
    },
    1261: {
        "id": 1261,
        "title": "完工申报",
        "src": "/production/completion/report/",
        "pid_id": 1253,
        "sort": 1281,
        "status": 1
    },
    1262: {
        "id": 1262,
        "title": "完工红冲",
        "src": "/production/completion/red-flush/",
        "pid_id": 1253,
        "sort": 1282,
        "status": 1
    },
    1263: {
        "id": 1270,
        "title": "成品入库",
        "src": "/production/product/receipt/",
        "pid_id": 1253,
        "sort": 1283,
        "status": 1
    },
    1271: {
        "id": 1271,
        "title": "AI智能中心",
        "src": "/ai/",
        "pid_id": 0,
        "sort": 129,
        "status": 1
    },
    1272: {
        "id": 1272,
        "title": "AI模型配置",
        "src": "/ai/config/models/",
        "pid_id": 1271,
        "sort": 131,
        "status": 1
    },
    1273: {
        "id": 1273,
        "title": "AI任务管理",
        "src": "/ai/tasks/",
        "pid_id": 1271,
        "sort": 132,
        "status": 1
    },
    1274: {
        "id": 1274,
        "title": "企业网盘",
        "src": "/disk/",
        "pid_id": 0,
        "sort": 134,
        "status": 1
    },
    1275: {
        "id": 1275,
        "title": "网盘首页",
        "src": "/adm/disk/",
        "pid_id": 1274,
        "sort": 135,
        "status": 1
    },
    1276: {
        "id": 1276,
        "title": "个人文件",
        "src": "/adm/disk/personal/",
        "pid_id": 1274,
        "sort": 136,
        "status": 1
    },
    1259: {
        "id": 1259,
        "title": "共享文件",
        "src": "/adm/disk/share/",
        "pid_id": 1274,
        "sort": 137,
        "status": 1
    },
    1260: {
        "id": 1260,
        "title": "回收站",
        "src": "/adm/disk/recycle/",
        "pid_id": 1274,
        "sort": 139,
        "status": 1
    },
    1261: {
        "id": 1261,
        "title": "员工管理",
        "src": "/user/employee/",
        "pid_id": 1107,
        "sort": 13,
        "status": 1
    },
    1262: {
        "id": 1262,
        "title": "资产管理",
        "src": "/oa/assets/borrow/",
        "pid_id": 1123,
        "sort": 18,
        "status": 1
    },
    1263: {
        "id": 1263,
        "title": "AI工作流",
        "src": "/ai/workflow/",
        "pid_id": 1271,
        "sort": 133,
        "status": 1
    },
    # 审批流程菜单 - 个人办公
    1300: {
        "id": 1300,
        "title": "审批流程",
        "src": "javascript:;",
        "pid_id": 1162,
        "sort": 55,
        "status": 1
    },
    1301: {
        "id": 1301,
        "title": "审批类型",
        "src": "/approval/approval_type/",
        "pid_id": 1300,
        "sort": 1,
        "status": 1
    },
    1302: {
        "id": 1302,
        "title": "审批流程",
        "src": "/approval/approvalflow/",
        "pid_id": 1300,
        "sort": 2,
        "status": 1
    },
    1303: {
        "id": 1303,
        "title": "我的审批",
        "src": "/approval/my/",
        "pid_id": 1300,
        "sort": 3,
        "status": 1
    },
    1304: {
        "id": 1304,
        "title": "发起审批",
        "src": "/approval/apply/",
        "pid_id": 1300,
        "sort": 4,
        "status": 1
    },
    1305: {
        "id": 1305,
        "title": "待我审批",
        "src": "/approval/pending/",
        "pid_id": 1300,
        "sort": 5,
        "status": 1
    },
    # 消息管理菜单 - 个人办公
    1400: {
        "id": 1400,
        "title": "消息管理",
        "src": "javascript:;",
        "pid_id": 1162,
        "sort": 56,
        "status": 1
    },
    1401: {
        "id": 1401,
        "title": "消息中心",
        "src": "/message/page/",
        "pid_id": 1400,
        "sort": 1,
        "status": 1
    },
    1403: {
        "id": 1403,
        "title": "通知偏好",
        "src": "/message/preference/",
        "pid_id": 1400,
        "sort": 2,
        "status": 1
    },
    1404: {
        "id": 1404,
        "title": "消息统计",
        "src": "/message/stats/page/",
        "pid_id": 1400,
        "sort": 3,
        "status": 1
    }
}

# 菜单树结构
def get_menu_tree():
    """构建菜单树结构"""
    menu_tree = []
    menu_map = {}
    
    # 构建菜单映射
    for menu_id, menu in system_menus.items():
        menu_map[menu_id] = menu.copy()
        menu_map[menu_id]['submenus'] = []
    
    # 构建菜单树
    for menu_id, menu in menu_map.items():
        if menu['pid_id'] == 0:
            menu_tree.append(menu)
        else:
            parent = menu_map.get(menu['pid_id'])
            if parent:
                parent['submenus'].append(menu)
    
    return menu_tree

