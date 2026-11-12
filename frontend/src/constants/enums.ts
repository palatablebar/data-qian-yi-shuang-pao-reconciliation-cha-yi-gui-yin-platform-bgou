/** 共享枚举（前端副本，后端唯一来源：backend/src/constants/enums.py）。
 *  出现位置：Badge/StatusSeal 配色、筛选 chip、批次状态机文案、tickets 状态机、README。 */
export const ROLE_LABELS: Record<string, string> = {
  admin: '迁移负责人',
  analyst: '数据开发',
  viewer: '审计',
};

export const BATCH_STATUS_LABELS: Record<string, string> = {
  pending: '待运行',
  running: '对账中',
  completed: '已完成',
  failed: '失败',
};

export const BUCKET_STATUS_LABELS: Record<string, string> = {
  match: '一致',
  mismatch: '不一致',
  empty: '空桶',
};

export const DIFF_TYPE_LABELS: Record<string, string> = {
  missing: '缺失行',
  extra: '多出行',
  type_truncated: '类型截断',
  precision_loss: '精度丢失',
  encoding: '编码差异',
  value_shift: '值漂移',
  duplicate_key: '主键重复',
};

export const TICKET_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  submitted: '待审批',
  approved: '已批',
  rejected: '驳回',
};

export const SIGNOFF_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  signed: '已签核',
};

export const SIGNOFF_FRESHNESS_LABELS: Record<string, string> = {
  fresh: '材料有效',
  stale: '材料过期',
};

export const STALE_REASON_LABELS: Record<string, string> = {
  batch_rerun: '批次冻结后重跑，对账结果已改写',
  batch_status: '批次状态与冻结时不一致',
  ticket_changed: '引用的已审批修复单发生变更',
  ticket_new: '冻结后出现覆盖本批次差异的新修复单',
  diff_unexempted: '存在冻结后新增的未豁免差异',
  pair_core_changed: '核心表标记发生变化',
};

export const PAIR_STATUS_LABELS: Record<string, string> = {
  active: '启用',
  paused: '暂停',
};

export const FIELD_TYPE_LABELS: Record<string, string> = {
  string: '字符',
  numeric: '数值',
  datetime: '时间',
};

export const STRATEGY_LABELS: Record<string, string> = {
  checksum: '桶级 checksum',
  row_hash: '行级哈希',
};
