# 小米 8 换屏 TWRP / MIUI 9.9.3 适配

适用于 **Xiaomi Mi 8（dipper）+ MIUI 9.9.3 / Android 9**。本项目提供经过一台换屏小米 8 实测的 TWRP 3.7.0 重打包镜像，以及可检查、可重复执行的构建脚本。

**下载：[Releases](https://github.com/qiyueqixi/mi8-dipper-twrp-miui9-fix/releases)**。使用 `TWRP-3.7.0-dipper-MIUI-9.9.3-fix-v2.img`。

## 什么屏幕实测可用？

实测手机更换过屏幕，其实际活动驱动标识如下：

| 项目 | 真机结果 |
| --- | --- |
| 显示节点 | `dsi_ss_ea8074_notch_fhd_cmd_display` |
| 显示接口 | EA8074 系列接口 |
| 触控 compatible | `st,fts`，ST 驱动系列 |
| 触控地址 | I²C `0x49`，输入设备名 `fts` |
| 分辨率 | 1080 × 2248 |
| 实际设备树 | `Xiaomi Technologies, Inc. Dipper new MP v2.1` |

这些是**驱动接口标识**。不能据此认定实物是三星原装屏、某品牌 LCD、某商家转换屏，也无法确定实际面板生产厂商或料号。`fts` 这个名称本身也不能用于认定 FocalTech；本次已进一步读到 `st,fts`。

本项目验证的是上述一台换屏手机，其他替换屏、触控芯片和 ROM 组合仍需单独测试。

## 解决了哪些问题？

| 问题 | 处理与证据 |
| --- | --- |
| 官方 TWRP 3.7.0 临时启动后未进入界面，随后回到 MIUI | 换用该 ROM 的官方 recovery 内核及全部 22 个 Dipper DTB 后，可以进入 TWRP 用户空间。无法仅凭这个结果确定原版失败的唯一原因。 |
| 初版重打包镜像卡在 TWRP 标志页 | ADB 日志定位到 Keymaster `Configure failed`（`-38`），TWRP 一直等待解密服务。 |
| 解密服务因版本信息不匹配而退出 | 把 `ro.build.version.release=16.1.0` 改为 `9`，`ro.build.version.security_patch=2099-12-31` 改为 `2019-09-01`。内存验证和 v2 独立启动均显示 Keymaster 正常、Data 解密成功。 |
| 本机 Windows USB 3.0 接线后提示 `Press any key to shutdown` | 为硬件 `18D1:D00D:0100` 添加设备专用 USB 枚举兼容设置，接线和 fastboot 传输恢复。此项是电脑补丁，不是 REC 内核补丁。 |

本镜像保留官方 MIUI 9.9.3 recovery 的内核，只筛选保留 22 个 Dipper DTB，并采用 TeamWin 3.7.0_9-0 ramdisk。它是**重打包适配**，没有宣称重新编译或修复所有换屏驱动。

## 实测范围与限制

2026-11-06，在已解锁的 dipper 上通过 `fastboot boot` 临时启动 v2，未执行运行时属性修补：

- 成功进入 TWRP 只读提示页及菜单。
- 用户确认菜单显示和触摸操作正常。
- Keymaster 状态为 `running`。
- 日志显示 `User 0 Decrypted Successfully`、`Data successfully decrypted`。
- ADB 连接正常。
- **MTP 文件传输尚未修复**，日志显示 USB 驱动启动失败；可使用 ADB 传输文件。
- 内核出现过触控自动更新固件失败的日志；两轮实测触控正常，但本项目没有修改触控自动更新逻辑。
- 尚未验证刷入 recovery 后的持久启动、刷 ROM、清除数据、制作或恢复备份。

这是单台手机、指定 ROM 的测试结果。其他 Android / MIUI / 安全补丁版本不能直接套用这组 Keymaster 属性，尤其不能把本镜像作为新版原生 ROM 的通用安装 recovery。

## 临时启动

确认机型为 `dipper`，使用 Google platform-tools：

```text
fastboot getvar product
fastboot boot TWRP-3.7.0-dipper-MIUI-9.9.3-fix-v2.img
```

进入 TWRP 后可选择保持只读。`fastboot boot` 不会将镜像写入 recovery 分区，但 recovery 启动后可能挂载或写入数据分区，不能等同于整个过程绝对不写数据。

本项目没有提供自动刷入、解锁、格式化或清除分区脚本。

## 校验

文件大小：**43,761,664 字节**，小于真机查询得到的 64 MiB recovery 分区。

```text
a560e39afb94baf38b5336c27ffe8a63e45213fd45b6c7011928d222609cbcb1  TWRP-3.7.0-dipper-MIUI-9.9.3-fix-v2.img
```

Windows：

```powershell
Get-FileHash .\TWRP-3.7.0-dipper-MIUI-9.9.3-fix-v2.img -Algorithm SHA256
```

## 重打包方法

运行环境为 Python 3，仅使用标准库。自行准备两个输入文件，执行：

```text
python tools/repack.py --stock-recovery recovery-miui-9.9.3.img --twrp twrp-3.7.0_9-0-dipper.img --output TWRP-3.7.0-dipper-MIUI-9.9.3-fix-v2.img
```

输入文件及来源：

| 输入 | 来源 / SHA-256 |
| --- | --- |
| MIUI 9.9.3 官方 recovery | 从 `dipper_images_9.9.3_20190904.0000.00_9.0_cn_8667d84222.tgz` 提取；`1b5cfb5e59d95caa6a53afad0d44ef678835a959915cfea9824444cf2f1b03fc` |
| 官方 TWRP 3.7.0_9-0 | [TeamWin 下载页](https://dl.twrp.me/dipper/twrp-3.7.0_9-0-dipper.img.html)；`81239b79c90ac4342195c80bd2e9132318583a9d6601203729f4c33921b52225` |

官方 ROM 的索引页面：[MIUI 9.9.3 for dipper](https://xmfirmwareupdater.com/miui/dipper/weekly/9.9.3/)。输入镜像必须匹配上述哈希。不同 Python/zlib 版本可能生成不同压缩字节，脚本会报告成品哈希是否与实测发布版本一致。

## USB 3.0 兼容补丁

仅用于 Windows 下 `VID_18D1&PID_D00D&REV_0100` 的 fastboot USB 枚举故障：

- 导入前备份 `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags\18D1D00D0100`。
- [补丁](usb3/mi8-usb3-fix.reg)增加 `SkipBOSDescriptorQuery`、`SkipContainerIdQuery` 两个 REG_BINARY 值 `01 00 00 00`。
- [撤销文件](usb3/undo-mi8-usb3-fix.reg)适用于上述两个值原先不存在的情况；若原先有值，应恢复自己的注册表备份。
- 不改绑或卸载 Android 驱动，不修改全局 USB 控制器设置。导入需要管理员权限，之后退出错误提示并重新进入 fastboot 再接线。
- 参考：[USB 3.0 fastboot workaround](https://github.com/zxhri/fix-fastboot)、[Microsoft USB device-specific registry settings](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-device-specific-registry-settings)。

## 上游与来源

- [TeamWin dipper 设备树](https://github.com/TeamWin/android_device_xiaomi_dipper/tree/7b136dfb141d2814580fff34856f1df3fc5036c9)。
- [TWRP recovery 源码](https://github.com/TeamWin/android_bootable_recovery)，dipper 版本基于 Android 9 构建线。
- [Xiaomi dipper Android P 内核开源分支](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/dipper-p-oss)。官方预编译内核字符串为 `4.9.112-perf-g35c9f36`；没有从该开源分支重新编译或证明逐字节可复现官方内核。
- boot image 头部布局参考 [AOSP mkbootimg](https://android.googlesource.com/platform/system/tools/mkbootimg)。

仓库自有脚本采用 [MIT License](LICENSE)。镜像中的内核、TWRP 和第三方组件继续受各自上游许可证约束，仓库许可证不重新授权这些组件。
