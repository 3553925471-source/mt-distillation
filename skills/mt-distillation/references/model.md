# 模型和输入约定

适用于二元混合物、恒定相对挥发度 alpha>1、恒摩尔流、全凝器、泡点回流、平衡部分再沸器和塔内单股进料。所有组成是轻组分摩尔分数，不是质量分数。由塔顶向下逐板计算，在操作线交点对应的最佳位置切换塔段。不支持非理想共沸体系、多组分、多股进料、侧线采出和任意指定进料板。

输入 JSON 字段：alpha、zF、xD、xW、q、R、F。必须满足 0<xW<zF<xD<1；F>0，实际 R>Rmin。q=1 为饱和液体，q=0 为饱和蒸气；q>1 和 q<0 可用，但工况仍须满足正气液流量、进料夹点控制和双塔段可行性检查。范围外工况会拒绝，不应自动调整输入以强行给出结果。可选 max_stages 默认 10000，tol 默认 1e-12。

相平衡：y=alpha*x/[1+(alpha-1)*x]；逆式 x=y/[alpha-(alpha-1)*y]。

物料衡算：D/F=(zF-xW)/(xD-xW)，W=F-D。
若题目提供 d=D/F，可先求 xW=(zF-d*xD)/(1-d)。若提供 R/Rmin，应使用 q 线与平衡线的交点求 Rmin 后转换为实际 R；不能把比值本身填进 R。

q 线使用 q*x-(q-1)*y=zF 的隐式形式，避免 q=1 除零。
进料夹点 (xe,ye) 给出 Rmin=(xD-ye)/(ye-xe)。精馏段 L=R*D，V=(R+1)*D；提馏段 L'=L+q*F，V'=V+(q-1)*F。
两条操作线为 y=(L/V)*x+D*xD/V 和 y=(L'/V')*x-W*xW/V'。

从 (xD,xD) 开始，先水平到相平衡曲线，再竖直到操作线。第一次水平步的终点 x<=xI 时，该级记为进料板，之后用提馏段操作线。首次 x<=xW 时停止。

若完整阶梯共 M 级，末水平步从 x_prev 到 x_last，f=(x_prev-xW)/(x_prev-x_last)：

- 内部总平衡级估算为 M-1+f，包含一个部分再沸器等效级。
- 对外报告的塔内理论板数为 M-2+f，不含再沸器；完整塔板数为 M-1。
- 最后一条阶梯仍绘出以解释终点，且不标塔板编号。编号从塔顶第 1 块开始。

末步线性插值是 MT 图解近似，不是精确满足塔底边界的整数级严格模拟。不能将该计数直接称为实际塔板数；实际塔板数还需要板效率等资料。JSON 保留内部平衡级数以便复核；图与结果文本报告塔内板数。Origin Parameters 页只保留塔内板数相关汇总。

F 的单位为 kmol/h。若题目只要求板数而没有 F，可明确采用 F=100 kmol/h 的计算基准。以 7-15 为例，D/F=0.34 对应 xW=0.0460606061；R/Rmin=1.4 对应 R=2.91221014。程序结果约为塔内 13.2758 块、完整 14 块、进料板第 8 块。进料板采用上述切换约定。

## 文件和退出码

- results.json：inputs、operating、summary、stages、staircase。
- stages.csv：包括最终再沸器等效末级的逐级组成，terminal_step=true 标记末级。
- staircase.csv、curves.csv：作图点；MT.png、MT.svg：MT 图。
- 计算结果.txt：塔内板数和操作参数。
- MT_origin.opju、MT_origin.png：成功启用 Origin 导出时生成。
- origin_error.txt：Origin 导出失败原因，普通结果仍保留。

0 成功；1 计算/环境错误；2 命令参数错误；3 仅 Origin 导出失败。

默认输出在用户 Documents/MT_Distillation/outputs。MT_OUTPUT_DIR 设置工作根目录，--out 在 CLI 中指定一个新的结果目录，在 GUI 中指定结果根目录。已有结果目录会被拒绝，以避免覆盖旧结果。
