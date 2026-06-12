# AutoPtCheckin Sites

AutoPtCheckin 的站点级签到适配层；输入站点 Cookie/UA/代理配置，输出统一 `(success, message)` 签到结果。

## Input / Output / Pos
- Input: MoviePilot 站点配置、Cookie、UA、代理、各站点签到页面/API。
- Output: `_ISiteSigninHandler` 子类，由插件入口动态加载并匹配站点域名。
- Pos: 站点差异封装层；通用签到无法准确处理的站点在这里单独适配。

## Files
- `__init__.py`: 定义 `_ISiteSigninHandler` 基类、页面获取与签到结果匹配工具。
- `52pt.py`: 52PT 站点签到适配。
- `btschool.py`: BTSchool 站点签到适配。
- `chdbits.py`: CHDBits 站点签到适配。
- `haidan.py`: 海胆 站点签到适配。
- `hares.py`: Hares 站点签到适配。
- `hdarea.py`: HDArea 站点签到适配。
- `hdbao.py`: HDBao 站点 POST attendance.php 签到适配。
- `hdchina.py`: HDChina 站点签到适配。
- `hdcity.py`: HDCity 站点签到适配。
- `hdsky.py`: HDSky 验证码签到适配。
- `hdupt.py`: HDUpt 站点签到适配。
- `mteam.py`: M-Team 站点签到适配。
- `nexushd.py`: NexusHD 站点 POST 签到适配。
- `opencd.py`: OpenCD 站点签到适配。
- `pterclub.py`: PterClub 站点签到适配。
- `pttime.py`: PTTime 站点签到适配。
- `siqi.py`: 思琪 站点签到适配。
- `tjupt.py`: TJUPT 站点签到适配。
- `ttg.py`: TTG 站点签到适配。
- `u2.py`: U2 站点签到适配。
- `yema.py`: 夜猫 站点签到适配。
- `zhuque.py`: 朱雀 站点签到适配。
