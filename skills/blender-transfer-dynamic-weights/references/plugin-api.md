# 插件调用参考

先定位用户的 `KK_Modder-BatchTool` 主仓库，将其绝对路径记为 `verified_repo_path`；说明文件是仓库根目录的 `WEIGHT_FEATURES_CN.md`。
不可把 `cache/repository-snapshots` 当主仓库。其他机器先定位仓库，不强制沿用路径。
测试产物按项目目录约定放入对应测试项目，通用技能/分析在 `garment-workflow`。

## 确认实际加载代码

在 Blender MCP 可用时，先发现工具，再用执行代码工具读取 `bpy` 和调用插件。
普通安装方式为 `from kk_vrc_cloth_tools import weights_features as wf`；检查 `wf.__file__`
和 `inspect.signature(wf.prepare_plan)` 是否含区域、手指和预留参数。
本项目旧安装目录/UI 未必同步，不从面板名称推断算法版本。

需要直接使用已核对的仓库源码、又不替换正在注册的插件时，可在 Blender 中隔离加载：

```python
import sys, types, importlib
from pathlib import Path
package_dir = Path(verified_repo_path) / 'kk_vrc_cloth_tools'
alias = 'garment_weight_source'
pkg = types.ModuleType(alias)
pkg.__path__ = [str(package_dir)]
sys.modules[alias] = pkg
core = importlib.import_module(alias + '.weight_features')
wf = importlib.import_module(alias + '.weights_features')
```

重复执行时检查模块缓存路径；更新源码后先 reload core，再 reload wf（及实际改过的采样模块），
不要误用旧函数。不调用整个插件 register/unregister，也不声称此举更新了安装目录。

## 调用顺序

以下变量均由 Agent 基于实际场景构造，不能照抄旧案例骨名：

```python
snapshot = wf.capture_snapshot(original_mesh, roles)
profiles = core.analyze(snapshot)
plan = wf.prepare_from_body(
    target_mesh, snapshot, target_body,
    body_map, dynamic_map, target_body_groups,
    sampling_confidence=confidence_by_vertex,
    indices=reviewed_vertex_indices,
    source_regions=source_regions,
    target_regions=target_regions,
    finger_policy=finger_policy,
    protected_components=None, region_modes=reviewed_region_modes,
)
# 检查 plan 后；场景改变需重新准备。
report = wf.apply_plan(target_mesh, plan)
```

- `roles`: 原组名 → BODY/DYNAMIC/DROP/IGNORE，所有非零组必须明确。
- `body_map` / `dynamic_map`: 原骨组名 → `{目标骨组名: 分配系数}`，每个映射内部归一化。
- 区域表：身体组名 → TORSO/ARM_L/ARM_R/LEG_L/LEG_R；包括头颈的 TORSO。
- `target_body_groups`: 允许的目标身体组集合，必须有有效变形骨且与动骨目标不重叠。
- `confidence_by_vertex`: 整数顶点索引 → 0..1，表示身体类别内部依赖采样程度，不是身体/动骨比例。缺省 0；稳定混合会强制映射。不要无条件所有顶点设 1。
- `indices=None` 表示全部；仅处理确定的范围时显式传入整数索引。
- `finger_policy`: `source_fingers`/`target_fingers` 是骨组名 → 指别标识；`enabled` 是获准指别列表；`disabled_map` 是关闭原手指到同侧非手指骨的映射。完整例子和细节读仓库说明。

需审查或清理候选时，使用插件的原生采样函数，然后传入 `prepare_plan`：

```python
native = importlib.import_module(alias + '.weights_transfer')
samples = native.transfer_source_body_weights_to_target(target_body, target_mesh, target_body_groups)
# 按有依据的语义清理 samples；保留处理原因。不在此实现自定义插值。
plan = wf.prepare_plan(
    target_mesh, snapshot, body_map, dynamic_map, target_body_groups,
    sampled_weights=dict(enumerate(samples)),
    sampling_confidence=confidence_by_vertex,
    indices=reviewed_vertex_indices,
    source_regions=source_regions, target_regions=target_regions,
    finger_policy=finger_policy, body_source=target_body,
    region_modes=reviewed_region_modes,
)
```

`prepare_from_body` 自动记录采样源状态；手动提供候选的 `prepare_plan` 无该来源信息，
调用者须保存采样时 `wf.stamp(target_body)` 并在写入前复核，不可把旧样本用于已变化身体。
准备过程中需保证目标未变化。快照和计划可 JSON 保存，加载后的候选/置信度索引需转回整数。

## 预览与验证

读取 `summary`、`skipped`、`region_budgets`、`regional_fallback`、
`preserved_finger_weights`、`writes`。逐顶点检查零类别、原无手指顶点、动骨比例。
不要把变化顶点数等同于质量验收。

写入拒绝过期计划、锁定的受管组、共享网格、多 Armature、骨骼包络、修改器遮罩及
未分类的有效目标影响。先弄清问题，不自动解锁、删骨或移除修改器。
检查失败会回滚该次权重写入；不会自动保存 blend。

`protected_components` 在 core 与两个准备入口均预留；非 None 报 `NotImplementedError`。
它不是已实现的稳定分量提取器。遇到技能描述的复合模式时提醒用户，再决定是否开发。

## 新 UI 与优化接口

插件 0.2 使用 `Scene.kkvrc_weight_workflow`，详细流程及参数见 [优化与 UI 调用参考](optimization-workflow.md)。初值 API 的 `region_modes` 是显式顶点模式表，不等同于优化导出的 `reviewed_patterns`。目标白名单通过 `body_source` 实际权重核对；调用 `prepare_plan` 时必须提供 `body_source`。
