# 衣物运动响应优化器 v1

这是现有六类预算迁移之后的可选精修阶段，提供 Python API 和离线求解 CLI。源码已接入插件包；旧 UI 不会自动调用它，已安装的 Blender 插件副本也不会随源码自动更新。

## 已实现范围

**身体骨准入硬条件**：从实际目标素体的非零权重建立白名单，导出拒绝违规初值，离线求解和验证拒绝违规候选，最终计划及写入再次检查素体状态与白名单。保留衣物动骨使用独立显式集合；身体手指同样须在白名单内。原生传递候选和语义映射均不能引入集合外身体骨。

用于驱动姿态的控制骨与接收权重的蒙皮骨是两个集合。`bone_map`、`poses` 可以引用零身体权重的关节骨；`target_names` 和局部 `region_bones` 不可以借此放开。旧版不含白名单合同的优化导出／写入计划需重新生成。`prepare_supported_initial` 可先按审核后的同类别映射修复初值，保持六类预算和动骨影响，再开始优化。

- 初值使用已审核的映射／原生最近面插值结果，不随机初始化权重。需要空间权重传递时，仍只允许 Blender `POLYINTERP_NEAREST`。
- OSQP 稀疏二次规划：每个顶点独立拥有参数，通过网格边上的权重**修正量**平滑项联合求解。锐边不加入平滑边集合。
- 六类预算（躯干、左右臂、左右腿、动骨）逐顶点守恒；保留动骨和启用手指的每根骨权重固定。零预算类别不能从邻近表面获得影响。
- 验收范围遵循用户于 2026-09-18 的补充：目的是换素体后复现原响应。纯动骨顶点退出接触约束及运动误差验收，相关碰撞仅作诊断；不得为了修复它们而改变原动骨设计。混合交接处仍参与身体权重优化，不能因含少量动骨就整片排除。全为纯动骨顶点的面才豁免面相交检查，跨越边界的面继续检查。
- 候选骨来自现有权重和一环邻域的同类证据。选区之外不改权重。
- 固定动作下的 LBS 响应拟合、初值正则、面积加权，以及带信赖域的接触半空间迭代。
- 身体三角面精确最近点查询；接触可包含衣物顶点和三角面重心／边中点。独立 Blender BVH 检查面相交，避免只数穿入的顶点。
- 常见姿态组与随机姿态组分别归一化，随机组总权重为常见组的 0.2；每组内支持 `weight`。holdout 姿态完全排除在求解之外。
- 采样后恢复姿态通道和骨架显示模式。导出、求解、验证、生成写入计划分离；写入走原有回滚接口。

不实现动力学参数识别、任意骨架的自动动作重定向或神经网络训练。未知／叠加混合权重模式仍须先由 Agent 逐点分析或人工处理，不能通过设置一个字符串冒充完成审核。`protected_components` 仍是未实现的预留接口。

## 坐标与体型差异

源身体和目标身体不需要相同拓扑。当前适配器要求**原衣物与已雕刻适配衣物**拥有可靠的逐顶点对应、相同边和面索引；仅顶点数相同不够。发生重拓扑／细分后，应先另行建立对应，当前接口会拒绝拓扑不一致。

全部采样点先通过对象世界矩阵转换，不直接比较两个对象的局部坐标。骨架蒙皮矩阵包含骨架世界矩阵及其逆矩阵；求解前检查数值 LBS 与 Blender 求值结果是否一致。

对顶点 v，源／目标附着框架分别记为 Hs、Ht。框架保留刚性旋转与平移，尺度放到局部形变映射 J 中。参考位置为：

```text
qs(p) = inverse(Hs(p)) * source_posed(v,p)
qt(0) = inverse(Ht(0)) * target_sculpted_rest(v)
Jlocal = transpose(Rt(0)) * Jworld(v) * Rs(0)
reference(v,p) = Ht(p) * [qt(0) + Jlocal * (qs(p) - qs(0))]
```

这使静止参考严格等于雕刻后的目标衣物，而不是要求目标回到原衣物的绝对位置。只迁移相对于附着部位的运动残差。

Jworld 使用原衣物／已适配衣物一环边的成对坐标拟合，因此能够表示局部拉长、变宽和雕刻改形。曲面缺少法向维度，使用面法向观测和骨架先验正则；反射、退化或极端尺度拟合回退到附着骨架的旋转／长度比并报告顶点数量。该法向厚度映射是近似，不能从二维表面唯一恢复三维体积变形。

附着框架默认取源顶点最强的非手指身体影响；纯动骨顶点沿父链找身体附着骨。目标框架通过显式 `bone_map` 取得。躯干分段不同通过 `poses[].controls` 表达：例如源一根胸骨的动作可以由目标两根脊柱按比例共同实现。比例须审核，不能把“相同欧拉角”当作相同宏观动作。当前还没有多框架连续融合或自动校准动作的功能。

## 调用步骤

Blender 内只需要其自带 NumPy。外部 Python 安装 `requirements-optimizer.txt`；不要将系统 Python 的二进制依赖直接塞入不同版本的 Blender Python。

```python
import json
from pathlib import Path
import numpy as np
from kk_vrc_cloth_tools import weights_optimization as api

# source、target、body 是已检查的明确对象；config 是审核后的语义和动作配置。
# config 必含 roles、bone_map、source_regions、target_regions、finger_policy、
# poses、reviewed_patterns，可选 selected。
arrays, metadata = api.export_context(source, target, body, **config)
directory = Path(context_directory)
directory.mkdir(parents=True, exist_ok=True)
np.savez_compressed(directory / 'context.npz', **arrays)
(directory / 'context.json').write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
```

角色沿用 BODY／DYNAMIC／DROP／IGNORE。`source_regions`、`target_regions` 将身体骨映射到 TORSO、ARM_L、ARM_R、LEG_L、LEG_R；动骨由 roles 识别。`finger_policy` 沿用六类接口中的 `source_fingers`、`target_fingers` 和 `enabled`。当前适配器要求动骨迁移后同名。

姿态示例（名称仅示意，不写死 VRC／KK 骨名）：

```python
pose = {
    'name': 'torso_bend', 'kind': 'common', 'weight': 1.0,
    'controls': [{
        'source': [('source_chest', 1.0)],
        'target': [('target_spine_lower', 0.5), ('target_spine_upper', 0.5)],
        'axis': [1, 0, 0], 'degrees': 15,
    }],
}
```

`axis` 是静止世界参考轴，适配器转到各骨局部轴。采样自动加入静止姿态。必须另外提供 `kind='holdout'` 的姿态，随机姿态在调用端使用固定且不同的种子生成。

外部运行：

```powershell
$env:PYTHONPATH='D:\Program\modding\cache\python\weight-optimization'
python D:\Program\modding\KK_Modder-BatchTool\kk_vrc_cloth_tools\optimizer_cli.py CONTEXT_DIRECTORY
python D:\Program\modding\KK_Modder-BatchTool\kk_vrc_cloth_tools\optimizer_cli.py CONTEXT_DIRECTORY --contacts
```

第一条产生 `candidate.npz`、`report.json`。在 Blender 内对它运行下面的独立验证并保存为 `validation.json`；第二条才可利用已发现的相交面添加面内采样，产生 `contact_candidate.npz`、`contact_report.json`。第一条只是无接触基线，不代表可直接写入。若新增相交面，重新验证并补充接触样本；不允许把未验收候选当作成功。

```python
from kk_vrc_cloth_tools import optimizer_validation, weights_features

with np.load(directory / 'contact_candidate.npz') as z:
    candidate = {k: z[k] for k in z.files}
report = json.loads((directory / 'contact_report.json').read_text(encoding='utf-8'))
validation = optimizer_validation.validate(arrays, metadata, candidate, report)
# 先存档 validation。失败时停止，不能手动把 accepted 改成 True。
if validation['accepted']:
    plan = api.prepare_optimized_plan(target, arrays, metadata, candidate['weights'], validation)
    # 在任务授权范围内，并另行完成所需叠穿／外观检查后执行：
    weights_features.apply_plan(target, plan)
```

求解报告始终不是写入许可。验证会重新计算候选位置，校验数据／参考摘要、六类预算、固定权重、身体影响区域的独立姿态误差与面相交。纯动骨区域必须维持原候选基线的运动位置，其碰撞数量单独记录为 excluded；冻结的身体顶点不会因此获得豁免。计划生成及最终写入均检查源、目标和身体是否已变化；不自动保存 blend。

需要保留原件对比时，先用 `copy = target.copy(); copy.data = target.data.copy()` 建立并链接独立副本，保持变换／修改器／原权重完全相同，再调用 `api.prepare_optimized_plan(target, arrays, metadata, candidate['weights'], validation, destination=copy)`，最后 `weights_features.apply_plan(copy, plan)`。接口会检查副本与验收基线一致，重新生成副本专用计划，并在写入时再次检查原件状态；不要修改已有带摘要的计划来替换对象名。

## 失败及边界

- `fixed_contact_conflict`：范围内接触样本的支撑顶点全部冻结，无可优化影响；继续迭代无效。纯动骨样本已排除，不再触发这一失败。若旧报告仅因纯动骨样本报告冲突，新验证器会核对每个样本归属、QP 求解状态、动骨几何不变及范围内检查，再作新的验收，不改写旧报告。
- `subproblem_failed`：当前信赖域内的线性化子问题未成功求解。不是对原始非线性问题全局无解的证明。
- 求解器 `solved` 只表示 QP 得到解，不能保证所有接触消失；最终必须独立验收。
- 当前只支持单个未遮罩 LBS Armature、无活动形态键、无约束／动画驱动的显式采样骨架。DQS／Preserve Volume、修改器叠加和任意驱动骨架会被拒绝，不静默近似。
- 接触有符号距离来自最近面法向，要求身体表面法向可信；它不是任意开放／自交网格的内部判定证明。容差默认 1e-4 **世界单位**，不是固定毫米。
- 未实现衣物自碰撞、其他叠穿衣物碰撞、连续时间碰撞证明、最大骨影响数稀疏化。验证返回 `complete_garment_acceptance=False`，提醒额外验收；若输出平台要求限制骨数量，剪枝后必须重新求解和验收。
- 当前衣物对应由资产来源和拓扑共同确认；API 不能识别一个刻意保留相同拓扑但语义被调换的顶点表。

## 当前夹克实测

**历史结果说明（2026-09-18 修订）：** 下述早期轮次曾把源上下臂 support 权重排除，动作误差是相对于不完整源参考计算的，不能据此证明复现原模型。当前版本保留全部有效源变形贡献，并以 Blender 求值的 `actual_source` 进行独立核验；旧上下文必须重新导出。统一规则及两张拓扑表的定位见 [VRC 权重结构定义](VRC_WEIGHT_SCHEMA_CN.md)。

2026-09-18，在 `Jacket(Open)` → `Jacket(Open).001`、目标 `o_body_a_0` 上采样。源裸素体不在当前场景，使用源骨架和成对衣物坐标作运动参考；目标身体使用场景求值网格。

8969 个顶点、29419 个自由变量、15 个姿态（其中 3 个独立验证）。数值 LBS 与 Blender 最大偏差约 3.9e-7 世界单位，静止参考偏差约 6.8e-16，六类份额最大误差约 4.0e-8。面积加权候选的独立姿态 RMS 从约 0.001423 降至约 0.001386，约改善 2.6%；这是所采样姿态和参考构造下的结果，不能外推为通用质量提升。

前屈姿态原基线已存在 16 对面相交，约 0.000428 世界单位的最大采样穿入深度，相关顶点由 `Jacket_B1_L.003`／`Jacket_B1_R.003` 完全控制。旧版把这些碰撞当作失败；用户确认这不属于身体权重优化范围。按新范围重新验证的报告独立保存为 `v1/contact_validation_body_scope.json`，旧报告保留供追溯。候选尚未写入当前场景，也未改衣物顶点、骨骼或贴图。试验导出、候选、验证和配置位于 `D:/Program/Neon Vertex/Garment-Transfer-Tests/jacket-transfer/weight-optimization`。

第一阶段候选后续已按用户要求写入独立副本 `Jacket(Open).Optimized`，原件保留。按修订范围验收通过：2063 个纯动骨顶点排除，16 对相交面和 6 个穿入样本均属排除区域；范围内为零。

## 第二阶段：T pose 末端响应

`export_context(..., selected=[...], local_refinement=policy)` 支持局部阶段。以第一阶段结果为初值，身体保持 T pose，仅动作合同中列出的末端骨发生相对运动；不混入肩、肘或躯干动作重新回归主体。

`policy` 包含：

- `region_bones`：每个六类身体区域获准调整的骨名列表。已有其他骨影响冻结；动骨和手指仍受原固定策略保护。候选骨须实际存在、归属一致，不能跨侧取权重。
- `delta_limits`：字符串顶点索引到最大单骨权重修正幅度的映射。选区外不写入；可通过邻接环逐级减小幅度来保护过渡边界。
- `pose_bones.source/target`：本阶段动作骨白名单。采样拒绝调用未授权的宏观骨骼。
- 可选 `prior`、`smooth`、`residual_scale`、`trust` 和 `max_contact_steps`：局部求解尺度及正则参数。运动误差只统计本轮选区，避免全衣物平均掩盖末端误差。

当前腕部试验：从原 Hand／Thumb 有效影响及现有掌骨影响确定核心，再沿同侧拓扑扩展两圈；左右各 781 个顶点。核心修正上限 1，两圈过渡分别为 0.25、0.06，外部冻结。只开放同侧既有前臂／腕／掌骨，保留大拇指逐骨权重。使用 19 个状态：静止、双向末端扭转／弯曲／侧偏以及左右独立组合验证。目标腕部辅助骨未被假设为自动随动，采样遵循当前 Blender 骨链实际行为。数据存于测试项目 `weight-optimization/stage2-wrist/`。

局部验收覆盖选中顶点及任何接触选区的跨边界面。纯动骨和选区外只保留诊断，但必须验证选区外权重及所有采样姿态的位置均未改变；不能用缩小范围掩盖对外围的破坏。此例 −30° 掌部弯曲时存在与袖带的旧碰撞，相关 20 个顶点全部在选区外、位置和权重均不变，因此保留而不改动袖带。

本轮独立末端验证 RMS 从 0.0079696 降到 0.0003862，最大误差从 0.0373576 降到 0.0034307（世界单位）；选区及跨边界面没有检测到穿模，局部修正上限、外围不变、动骨／大拇指固定检查通过。没有另行进行宏观姿态回归。结果写入独立副本 `Jacket(Open).WristRefined`，第一阶段副本保留；具体写入记录见 `stage2-wrist/writeback.json`。

## 测试命令

源辅助骨修正轮：`Jacket(Open).SourceSupportFinal` 保留原 4 根上下臂 support 的源运动贡献，在完整归一化源权重下重建初值，重跑主体与腕部局部两阶段。源动作与 Blender 实际求值最大偏差分别为 3.95e-7、2.87e-7 世界单位。腕部独立验证 RMS 0.0046955 → 0.00077734，六类预算误差小于 4.5e-8；34 根实际目标身体骨、41 根已审核衣物动骨，未引入无素体权重的身体骨。

左腕影响大于等于 50% 的最靠近肘部位置，以肘=0、手腕=1 的前臂投影表示：原衣物 0.9639、旧错误结果 0.7198、本轮 0.9662。原顶点 5535 的手骨份额为 3.3448%，本轮为 3.2424%，旧结果为 29.3355%。统计原衣物时使用所有有效变形骨的归一化份额，不能直接把未归一化原权重与最终权重比较。

恢复源辅助骨后，混合顶点的动骨/手指绝对份额也以完整原权重重新归一化；不沿用旧 DROP 配置计算的份额。两次求解分别固定自己的正确初值中的动骨与启用拇指贡献。模型、UV、法线和骨架未改；旧结果保留。报告归档在测试项目 `weight-optimization/source-support-round/`。代码从仓库隔离加载，不等于已同步 Blender 已安装插件。

白名单重跑结果（2026-09-18）：从未优化的适配衣物副本修复 2088 个顶点上的 9 根违规身体骨份额，再重跑主体与 T pose 末端两阶段。最终 `Jacket(Open).BodyWhitelistFinal` 实际使用 34 根素体已有权重的身体骨及 41 根保留衣物动骨，违规身体骨为零；9 个已清空的违规组也已从最终副本移除，骨架节点未删除。动骨／指定手指权重保持不变，两阶段分别通过其范围内的接触和独立姿态验收。末端 RMS 0.0079696 → 0.0003862，最终六类误差小于 4.5e-8。旧副本保留，当前场景未自动保存。导出、报告和写入记录位于测试项目 `weight-optimization/body-whitelist-round/stage1` 与 `stage2`。

```powershell
# 外部 Python（设置上述 PYTHONPATH 后）
python tests/test_weight_optimizer.py
# 在仓库工作目录，通过 Blender 自带 Python 测试集成及旧预算算法
blender --background --factory-startup --python tests/test_optimizer_blender.py
blender --background --factory-startup --python tests/test_weight_features.py
```

覆盖已知权重反解、局部坐标与非均匀雕刻、固定份额、选区边界、最近面查询、顶点／面内接触、冻结接触诊断，以及 Blender 世界变换、状态恢复和过期写入保护。
