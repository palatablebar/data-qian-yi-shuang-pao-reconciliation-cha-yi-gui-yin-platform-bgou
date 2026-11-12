/** 页面文案常量：统一“底稿/复核”口吻，避免散落在页面里。 */
export const APP_TITLE = 'paritycheck · 双跑对账底稿';
export const APP_SUBTITLE = '明川银行 · 数据中台迁移组';
export const CASE_NO = '案卷 PC-2026-11 · 双跑验收';
export const WRITE_HINTS: Record<string, string> = {
  admin: '迁移负责人：可发起批次、维护映射、审批修复单',
  analyst: '数据开发：可发起批次、下钻差异、提交修复单（不可审批）',
  viewer: '审计：只读查看对账结论与导出底稿',
};
export const KNOWN_FAILURE_LABELS: Record<string, string> = {
  null_primary_key: '源表主键含 NULL（null_primary_key）',
  pair_inactive: '表对已暂停（pair_inactive）',
  no_pairs: '批次未包含表对（no_pairs）',
  duplicate_key: '主键重复（duplicate_key）',
};
