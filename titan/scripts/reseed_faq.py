#!/usr/bin/env python3
"""Re-seed FAQ data with proper UTF-8 encoding."""
import os, sys, django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
django.setup()

from django.db import connections

c = connections['default'].cursor()
c.execute("SET NAMES utf8mb4")

# ── Fix category icons ──
icons = {
    'DOWNLOAD': '📥',
    'PAYMENT': '💳',
    'APP_ERROR': '📱',
    'SPEED': '⚡',
    'WINDOWS_FAIL': '🖥️',
    'CONCURRENT': '👥',
    'LOGIN': '🔑',
}
for key, icon in icons.items():
    c.execute('UPDATE tbl_faq_category SET icon=%s WHERE category_key=%s', [icon, key])
print('Icons updated')

# ── Re-insert FAQ items ──
items = [
    # (category_id, sort_order, content_ko, content_zh, content_en)
    (1, 1,
     # ── DOWNLOAD KO ──
     """<h6>Android (안드로이드)</h6>
<p>타이탄VPN은 구글 플레이스토어에서 검색되지 않습니다.<br>아래 방법으로 APK를 직접 설치해주세요.</p>
<ul>
<li>휴대폰 브라우저에서 다음 주소 접속: <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a></li>
<li>[다운로드] 클릭 → APK 파일 다운로드</li>
<li>"출처를 알 수 없는 앱" 허용 후 설치<br><small>(설정 → 보안 → 알 수 없는 출처)</small></li>
<li>앱 실행 → 아이디/비밀번호 입력 → 서버 선택 → 연결</li>
</ul>

<h6>iOS (아이폰/아이패드)</h6>
<ul>
<li>앱스토어에서 "Titan VPN" 검색</li>
<li>설치 후 앱 실행</li>
<li>아이디/비밀번호 입력 → 서버 선택 → 연결</li>
</ul>
<div class="notice">
⚠️ 중국 Apple ID로는 타이탄VPN이 검색되지 않습니다.<br>
→ Apple ID 지역을 한국으로 임시 변경하거나<br>
→ 타이탄 공용 Apple ID를 사용하세요. (공용ID 문의는 고객센터)
</div>

<h6>Windows (윈도우 PC)</h6>
<ul>
<li>PC 브라우저에서 <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a> 접속</li>
<li>[Windows 다운로드] 클릭 → 설치파일 실행</li>
<li>설치 후 아이디/비밀번호 입력 → 서버 선택 → 연결</li>
</ul>

<h6>macOS (맥북)</h6>
<ul>
<li>위 사이트에서 [macOS 다운로드] 클릭</li>
<li>DMG 파일 실행 → 응용프로그램에 드래그</li>
<li>앱 실행 → 아이디/비밀번호 입력 → 연결</li>
</ul>
<div class="notice">
⚠️ 보안 정책으로 설치가 막힐 경우:<br>
→ Mac 설정 → 개인 정보 보호 및 보안 → 하단 "확인 없이 열기" 클릭
</div>
<p class="mt-3">
※ 중국에서 접속이 안될 경우 보조 주소 사용: <a href="https://www.titanvpn.kr" target="_blank">https://www.titanvpn.kr</a>
</p>""",
     # ── DOWNLOAD ZH ──
     """<h6>Android (安卓)</h6>
<p>Titan VPN无法在Google Play商店搜索到。<br>请按照以下方法直接安装APK。</p>
<ul>
<li>在手机浏览器中打开: <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a></li>
<li>点击[下载] → 下载APK文件</li>
<li>允许"未知来源"后安装<br><small>(设置 → 安全 → 未知来源)</small></li>
<li>启动应用 → 输入ID/密码 → 选择服务器 → 连接</li>
</ul>

<h6>iOS (iPhone/iPad)</h6>
<ul>
<li>在App Store搜索"Titan VPN"</li>
<li>安装后启动应用</li>
<li>输入ID/密码 → 选择服务器 → 连接</li>
</ul>
<div class="notice">
⚠️ 使用中国Apple ID无法搜索Titan VPN。<br>
→ 临时将Apple ID地区更改为韩国，或<br>
→ 使用Titan提供的共享Apple ID。（联系客服获取共享ID）
</div>

<h6>Windows (电脑)</h6>
<ul>
<li>在PC浏览器中打开 <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a></li>
<li>点击[Windows下载] → 运行安装程序</li>
<li>安装后输入ID/密码 → 选择服务器 → 连接</li>
</ul>

<h6>macOS (MacBook)</h6>
<ul>
<li>在上述网站点击[macOS下载]</li>
<li>运行DMG文件 → 拖入应用程序</li>
<li>启动应用 → 输入ID/密码 → 连接</li>
</ul>
<div class="notice">
⚠️ 如果因安全策略被阻止安装:<br>
→ Mac设置 → 隐私与安全 → 点击底部"仍要打开"
</div>
<p class="mt-3">
※ 中国无法访问时请使用备用地址: <a href="https://www.titanvpn.kr" target="_blank">https://www.titanvpn.kr</a>
</p>""",
     # ── DOWNLOAD EN ──
     """<h6>Android</h6>
<p>Titan VPN is not available on the Google Play Store.<br>Please install the APK directly using the method below.</p>
<ul>
<li>Open the following URL in your phone browser: <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a></li>
<li>Click [Download] → Download the APK file</li>
<li>Enable "Unknown Sources" and install<br><small>(Settings → Security → Unknown Sources)</small></li>
<li>Launch the app → Enter ID/Password → Select server → Connect</li>
</ul>

<h6>iOS (iPhone/iPad)</h6>
<ul>
<li>Search for "Titan VPN" on the App Store</li>
<li>Install and launch the app</li>
<li>Enter ID/Password → Select server → Connect</li>
</ul>
<div class="notice">
⚠️ Titan VPN is not searchable with a China region Apple ID.<br>
→ Temporarily change your Apple ID region to Korea, or<br>
→ Use a shared Apple ID provided by Titan. (Contact support for shared ID)
</div>

<h6>Windows PC</h6>
<ul>
<li>Visit <a href="https://titan.jobjapan.com" target="_blank">https://titan.jobjapan.com</a> in your PC browser</li>
<li>Click [Windows Download] → Run the installer</li>
<li>After installation, enter ID/Password → Select server → Connect</li>
</ul>

<h6>macOS (MacBook)</h6>
<ul>
<li>Click [macOS Download] from the site above</li>
<li>Run the DMG file → Drag to Applications</li>
<li>Launch the app → Enter ID/Password → Connect</li>
</ul>
<div class="notice">
⚠️ If installation is blocked due to security:<br>
→ Mac Settings → Privacy & Security → Click "Open Anyway" at the bottom
</div>
<p class="mt-3">
※ If you cannot access the site from China, use the backup address: <a href="https://www.titanvpn.kr" target="_blank">https://www.titanvpn.kr</a>
</p>"""),

    (2, 2,
     # ── PAYMENT KO ──
     """<h6>상품 종류 및 가격</h6>
<p>👉 <a href="/price_table">가격표 보기</a></p>
<p><strong>▶ 한국 자동결제</strong></p>
<ul>
<li>1회선 (동시접속 1대): ￦8,300/월~</li>
<li>2회선 (동시접속 2대): ￦14,000/월~</li>
<li>6회선 (동시접속 6대): ￦43,300/월~</li>
</ul>
<p><strong>▶ 중국 알리페이 / 위챗페이</strong></p>
<ul>
<li>1회선 (동시접속 1대): ¥69/월~</li>
<li>2회선 (동시접속 2대): ¥99/월~</li>
<li>6회선 (동시접속 6대): ¥328/월~</li>
</ul>
<p>※ 3/6/12개월 장기 결제시 할인 적용</p>

<h6>결제 수단</h6>
<ul>
<li>신용카드 (한국 / 해외)</li>
<li>계좌이체</li>
<li>Alipay / WeChat Pay</li>
</ul>

<h6>연장 방법</h6>
<ul>
<li><a href="https://www.titanvpn.kr" target="_blank">titanvpn.kr</a> 로그인</li>
<li>[마이페이지] → [구독 연장]</li>
<li>상품/기간 선택 → 결제</li>
</ul>

<h6>환불 정책</h6>
<ul>
<li>결제 후 7일 이내 미사용시 전액 환불</li>
<li>사용 이력이 있으면 일할 계산 환불</li>
<li>고객센터 또는 kakaovpn@naver.com 으로 요청</li>
<li>채널톡 상담: <a href="https://titan.channel.io/" target="_blank">https://titan.channel.io/</a></li>
</ul>

<h6>결제가 반영되지 않나요?</h6>
<ul>
<li>카드/이체: 보통 5분 이내 반영</li>
<li>알리페이/위챗: 최대 10분 소요</li>
<li>10분 경과 후에도 미반영시: 결제 스크린샷 + 이메일을 고객센터로 전송</li>
</ul>""",
     # ── PAYMENT ZH ──
     """<h6>产品种类及价格</h6>
<p>👉 <a href="/price_table">查看价格表</a></p>
<p><strong>▶ 韩国自动付款</strong></p>
<ul>
<li>1线路（同时连接1台）: ￦8,300/月起</li>
<li>2线路（同时连接2台）: ￦14,000/月起</li>
<li>6线路（同时连接6台）: ￦43,300/月起</li>
</ul>
<p><strong>▶ 中国支付宝/微信支付</strong></p>
<ul>
<li>1线路（同时连接1台）: ¥69/月起</li>
<li>2线路（同时连接2台）: ¥99/月起</li>
<li>6线路（同时连接6台）: ¥328/月起</li>
</ul>
<p>※ 3/6/12个月长期付款享折扣</p>

<h6>支付方式</h6>
<ul>
<li>信用卡（韩国/国际）</li>
<li>银行转账</li>
<li>Alipay / WeChat Pay</li>
</ul>

<h6>续费方法</h6>
<ul>
<li>登录 <a href="https://www.titanvpn.kr" target="_blank">titanvpn.kr</a></li>
<li>[我的页面] → [续费订阅]</li>
<li>选择产品/期限 → 支付</li>
</ul>

<h6>退款政策</h6>
<ul>
<li>付款后7天内未使用可全额退款</li>
<li>已使用则按比例退款</li>
<li>通过客服或 kakaovpn@naver.com 申请</li>
<li>ChannelTalk咨询: <a href="https://titan.channel.io/" target="_blank">https://titan.channel.io/</a></li>
</ul>

<h6>付款未到账？</h6>
<ul>
<li>信用卡/转账: 通常5分钟内到账</li>
<li>支付宝/微信: 最多10分钟</li>
<li>超过10分钟未到账: 请将付款截图和邮箱发送至客服</li>
</ul>""",
     # ── PAYMENT EN ──
     """<h6>Products & Pricing</h6>
<p>👉 <a href="/price_table">View pricing page</a></p>
<p><strong>▶ Korean Auto-Payment</strong></p>
<ul>
<li>1 Line (1 simultaneous connection): from ￦8,300/month</li>
<li>2 Line (2 simultaneous connections): from ￦14,000/month</li>
<li>6 Line (6 simultaneous connections): from ￦43,300/month</li>
</ul>
<p><strong>▶ China Alipay / WeChat Pay</strong></p>
<ul>
<li>1 Line (1 simultaneous connection): from ¥69/month</li>
<li>2 Line (2 simultaneous connections): from ¥99/month</li>
<li>6 Line (6 simultaneous connections): from ¥328/month</li>
</ul>
<p>※ Discounts available for 3/6/12-month plans</p>

<h6>Payment Methods</h6>
<ul>
<li>Credit Card (Korean / International)</li>
<li>Bank Transfer</li>
<li>Alipay / WeChat Pay</li>
</ul>

<h6>How to Renew</h6>
<ul>
<li>Log in at <a href="https://www.titanvpn.kr" target="_blank">titanvpn.kr</a></li>
<li>[MyPage] → [Renew Subscription]</li>
<li>Select plan/period → Pay</li>
</ul>

<h6>Refund Policy</h6>
<ul>
<li>Full refund within 7 days of payment if unused</li>
<li>Pro-rated refund if service was used</li>
<li>Request via support or kakaovpn@naver.com</li>
<li>ChannelTalk consultation: <a href="https://titan.channel.io/" target="_blank">https://titan.channel.io/</a></li>
</ul>

<h6>Payment Not Reflected?</h6>
<ul>
<li>Card/Transfer: Usually reflected within 5 minutes</li>
<li>Alipay/WeChat: Up to 10 minutes</li>
<li>If not reflected after 10 minutes, please send a payment screenshot with your email to support</li>
</ul>"""),

    (3, 3,
     # ── APP_ERROR KO ──
     """<h6>앱이 실행되지 않을 때</h6>
<ul>
<li>앱 완전 종료 후 재실행</li>
<li>스마트폰 재부팅 후 다시 시도</li>
<li>앱 삭제 → 재설치 (데이터는 서버에 저장됨)</li>
</ul>

<h6>VPN이 연결되지 않을 때</h6>
<ul>
<li>다른 서버로 변경 시도</li>
<li>WiFi ↔ LTE/5G 전환</li>
<li>접속 해제 → 앱 종료 → 재실행 → 재접속</li>
</ul>

<h6>중국에서 접속이 안될 때</h6>
<ul>
<li>앱에서 서버 목록 새로고침</li>
<li>차이나모바일: KT 서버 시도</li>
<li>차이나유니콤: SK 서버 시도</li>
<li>차이나텔레콤: KT/SK 모두 시도</li>
<li>피크타임(오후 8시~12시)에는 속도 저하 가능</li>
</ul>

<h6>위 방법으로도 해결이 안된다면</h6>
<p>빠른 도움을 위해 아래 정보를 알려주세요:</p>
<ul>
<li>기기 종류 (Android/iPhone/PC)</li>
<li>국가/통신사 (예: 차이나모바일)</li>
<li>시도한 서버 이름</li>
<li>오류 메시지 또는 스크린샷</li>
</ul>""",
     # ── APP_ERROR ZH ──
     """<h6>应用无法启动</h6>
<ul>
<li>完全关闭应用后重新启动</li>
<li>重启手机后再试</li>
<li>卸载 → 重新安装（数据保存在服务器）</li>
</ul>

<h6>VPN无法连接</h6>
<ul>
<li>尝试切换到其他服务器</li>
<li>WiFi ↔ LTE/5G 切换</li>
<li>断开 → 关闭应用 → 重启 → 重新连接</li>
</ul>

<h6>在中国无法连接</h6>
<ul>
<li>在应用中刷新服务器列表</li>
<li>中国移动: 尝试KT服务器</li>
<li>中国联通: 尝试SK服务器</li>
<li>中国电信: KT和SK都试试</li>
<li>高峰时段（晚8点-12点）速度可能下降</li>
</ul>

<h6>以上方法都不行？</h6>
<p>为了更快帮助您，请提供以下信息：</p>
<ul>
<li>设备类型（Android/iPhone/PC）</li>
<li>国家/运营商（如：中国移动）</li>
<li>尝试的服务器名称</li>
<li>错误信息或截图</li>
</ul>""",
     # ── APP_ERROR EN ──
     """<h6>App Not Launching</h6>
<ul>
<li>Force close and relaunch the app</li>
<li>Reboot your device and try again</li>
<li>Uninstall → Reinstall (your data is stored on the server)</li>
</ul>

<h6>VPN Not Connecting</h6>
<ul>
<li>Try switching to a different server</li>
<li>Switch between WiFi ↔ LTE/5G</li>
<li>Disconnect → Close app → Relaunch → Connect</li>
</ul>

<h6>Cannot Connect from China</h6>
<ul>
<li>Refresh the server list in the app</li>
<li>China Mobile: Try KT servers</li>
<li>China Unicom: Try SK servers</li>
<li>China Telecom: Try both KT and SK</li>
<li>Speed may decrease during peak hours (8PM-12AM)</li>
</ul>

<h6>If still not working</h6>
<p>Please provide the following for faster support:</p>
<ul>
<li>Device type (Android/iPhone/PC)</li>
<li>Country/Carrier (e.g., China Mobile)</li>
<li>Server name you tried</li>
<li>Error message or screenshot</li>
</ul>"""),

    (4, 4,
     # ── SPEED KO ──
     """<h6>기본 점검 사항</h6>
<ul>
<li>VPN 끄고 일반 인터넷 속도 확인</li>
<li>다른 서버로 변경 시도</li>
<li>WiFi ↔ LTE/5G 전환</li>
<li>앱 종료 후 재실행</li>
</ul>

<h6>중국 통신사별 추천 서버</h6>
<ul>
<li>차이나모바일: KT 서버 추천</li>
<li>차이나유니콤: SK 서버 추천</li>
<li>차이나텔레콤: KT/SK 모두 시도</li>
</ul>

<h6>피크타임</h6>
<p>오후 8시~자정: 중국 전역 인터넷 혼잡 구간. 이 시간에는 속도가 느려질 수 있습니다. 오전/오후 시간대가 최적입니다.</p>

<h6>PC 사용자</h6>
<ul>
<li>IKEv2보다 OpenVPN이 더 안정적일 수 있음</li>
<li>백신/방화벽이 VPN 트래픽을 차단할 수 있음 — 일시 비활성화 시도</li>
</ul>

<h6>다른 VPN 앱 제거</h6>
<div class="notice">
⚠️ 다른 VPN 앱이 충돌을 일으켜 속도를 저하시킬 수 있습니다. 사용하지 않는 VPN 앱은 삭제해주세요.
</div>

<h6>WiFi 모뎀 재시작</h6>
<p>WiFi 사용 중이라면, 모뎀/공유기를 2~3분 끈 후 재시작하면 속도가 개선되는 경우가 많습니다.</p>""",
     # ── SPEED ZH ──
     """<h6>基本检查事项</h6>
<ul>
<li>关闭VPN检查普通网速</li>
<li>尝试切换到其他服务器</li>
<li>WiFi ↔ LTE/5G 切换</li>
<li>关闭应用后重启</li>
</ul>

<h6>中国运营商推荐服务器</h6>
<ul>
<li>中国移动: 推荐KT服务器</li>
<li>中国联通: 推荐SK服务器</li>
<li>中国电信: KT和SK都试试</li>
</ul>

<h6>高峰时段</h6>
<p>晚8点-午夜: 中国全境网络拥堵。此时段速度可能较慢。上午/下午时段最佳。</p>

<h6>PC用户</h6>
<ul>
<li>某些情况下OpenVPN可能比IKEv2更稳定</li>
<li>杀毒软件/防火墙可能会阻止VPN流量 — 尝试暂时禁用</li>
</ul>

<h6>删除其他VPN应用</h6>
<div class="notice">
⚠️ 其他VPN应用可能导致冲突并降低连接速度。请卸载不使用的VPN应用。
</div>

<h6>重启WiFi调制解调器</h6>
<p>使用WiFi时，关闭调制解调器/路由器2-3分钟后重启，通常可以改善速度。</p>""",
     # ── SPEED EN ──
     """<h6>Basic Troubleshooting</h6>
<ul>
<li>Check internet speed without VPN first</li>
<li>Try switching to a different server</li>
<li>Switch between WiFi ↔ LTE/5G</li>
<li>Close and relaunch the app</li>
</ul>

<h6>Recommended Servers by China Carrier</h6>
<ul>
<li>China Mobile: KT servers recommended</li>
<li>China Unicom: SK servers recommended</li>
<li>China Telecom: Try both KT and SK</li>
</ul>

<h6>Peak Hours</h6>
<p>8PM-Midnight: Internet congestion across China. Speed may be slower during these hours. Morning/afternoon is optimal.</p>

<h6>PC Users</h6>
<ul>
<li>OpenVPN may be more stable than IKEv2 in some cases</li>
<li>Antivirus/firewall may block VPN traffic — try disabling temporarily</li>
</ul>

<h6>Remove Other VPN Apps</h6>
<div class="notice">
⚠️ Other VPN apps may cause conflicts and slow down your connection. Please uninstall any unused VPN apps.
</div>

<h6>Restart WiFi Modem</h6>
<p>If using WiFi, turning off the modem/router for 2-3 minutes and restarting often improves speed.</p>"""),

    (5, 5,
     # ── WINDOWS KO ──
     """<h6>오류코드 809</h6>
<p>원인: 방화벽 또는 NAT 설정이 VPN 포트를 차단</p>
<ul>
<li>Windows 방화벽 → 고급 설정 → 인바운드 규칙 → UDP 500, 4500 허용</li>
<li>공유기 사용시 IPsec Passthrough 활성화</li>
<li>IKEv2 대신 OpenVPN 클라이언트 사용 시도</li>
</ul>

<h6>오류코드 812</h6>
<p>원인: 인증 실패 (아이디/비밀번호 오류 또는 만료)</p>
<ul>
<li>이메일과 비밀번호 확인</li>
<li><a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a> 에서 비밀번호 재설정</li>
<li>구독 기간 만료 여부 확인 (마이페이지)</li>
</ul>

<h6>오류코드 691</h6>
<p>원인: 계정 인증 실패 — 812 오류와 동일한 해결 방법</p>

<h6>RAS / 어댑터 오류</h6>
<ul>
<li>네트워크 어댑터 초기화: 설정 → 네트워크 → 상태 → 네트워크 초기화</li>
<li>PC 재부팅 후 재연결</li>
<li>IKEv2 VPN 연결 삭제 후 재생성</li>
</ul>

<h6>IKEv2 설정 가이드</h6>
<ul>
<li>설정 → 네트워크 → VPN → VPN 연결 추가</li>
<li>VPN 공급자: Windows (기본 제공)</li>
<li>서버: 제공된 서버 주소 입력</li>
<li>VPN 유형: IKEv2</li>
<li>로그인: 이메일/비밀번호 입력</li>
</ul>""",
     # ── WINDOWS ZH ──
     """<h6>错误代码809</h6>
<p>原因：防火墙或NAT设置阻止VPN端口</p>
<ul>
<li>Windows防火墙 → 高级设置 → 入站规则 → 允许UDP 500, 4500</li>
<li>使用路由器时启用IPsec Passthrough</li>
<li>尝试使用OpenVPN客户端替代IKEv2</li>
</ul>

<h6>错误代码812</h6>
<p>原因：认证失败（ID/密码错误或已过期）</p>
<ul>
<li>确认邮箱和密码</li>
<li>在 <a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a> 重置密码</li>
<li>检查订阅是否过期（我的页面）</li>
</ul>

<h6>错误代码691</h6>
<p>原因：账户认证失败 — 与812错误相同的解决方法</p>

<h6>RAS / 适配器错误</h6>
<ul>
<li>重置网络适配器：设置 → 网络 → 状态 → 网络重置</li>
<li>重启PC后重新连接</li>
<li>删除IKEv2 VPN连接后重新创建</li>
</ul>

<h6>IKEv2设置指南</h6>
<ul>
<li>设置 → 网络 → VPN → 添加VPN连接</li>
<li>VPN提供商：Windows（内置）</li>
<li>服务器：输入提供的服务器地址</li>
<li>VPN类型：IKEv2</li>
<li>登录：输入邮箱/密码</li>
</ul>""",
     # ── WINDOWS EN ──
     """<h6>Error Code 809</h6>
<p>Cause: Firewall or NAT blocking VPN ports</p>
<ul>
<li>Windows Firewall → Advanced → Inbound Rules → Allow UDP 500, 4500</li>
<li>If using a router, enable IPsec Passthrough</li>
<li>Try using OpenVPN client instead of IKEv2</li>
</ul>

<h6>Error Code 812</h6>
<p>Cause: Authentication failed (wrong ID/password or expired)</p>
<ul>
<li>Verify your email and password</li>
<li>Reset password at <a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a></li>
<li>Check if subscription has expired (MyPage)</li>
</ul>

<h6>Error Code 691</h6>
<p>Cause: Account authentication failed — same solutions as Error 812</p>

<h6>RAS / Adapter Error</h6>
<ul>
<li>Reset network adapter: Settings → Network → Status → Network Reset</li>
<li>Reboot PC and reconnect</li>
<li>Delete IKEv2 VPN connection and re-create it</li>
</ul>

<h6>IKEv2 Setup Guide</h6>
<ul>
<li>Settings → Network → VPN → Add VPN Connection</li>
<li>VPN Provider: Windows (built-in)</li>
<li>Server: Enter provided server address</li>
<li>VPN Type: IKEv2</li>
<li>Login: Enter email/password</li>
</ul>"""),

    (6, 6,
     # ── CONCURRENT KO ──
     """<h6>동시접속이란?</h6>
<p>하나의 계정으로 동시에 VPN을 연결할 수 있는 기기 수를 말합니다.</p>

<h6>플랜별 접속 수</h6>
<ul>
<li>1회선: 1대</li>
<li>2회선: 2대</li>
<li>6회선: 6대 (기기 종류 무관)</li>
</ul>

<h6>초과 시</h6>
<p>허용된 접속 수를 모두 사용 중이면 추가 접속이 차단됩니다. 다른 기기의 연결을 먼저 해제하세요.</p>

<h6>잔여 세션</h6>
<p>비정상 종료된 기기의 세션이 5~10분간 남아있을 수 있습니다. 즉시 초기화가 필요하면 고객센터에 문의하세요.</p>

<h6>업그레이드</h6>
<p><a href="/price_table">가격표 페이지</a>에서 플랜을 업그레이드하여 동시접속 수를 늘릴 수 있습니다.</p>""",
     # ── CONCURRENT ZH ──
     """<h6>什么是同时连接？</h6>
<p>指一个账户可以同时连接VPN的设备数量。</p>

<h6>各套餐连接数</h6>
<ul>
<li>1线路: 1台设备</li>
<li>2线路: 2台设备</li>
<li>6线路: 6台设备（任何设备类型）</li>
</ul>

<h6>超出时</h6>
<p>当所有允许的连接都在使用中时，额外连接将被阻止。请先断开其他设备。</p>

<h6>残留会话</h6>
<p>异常断开的设备会话可能保留5-10分钟后自动清理。如需立即重置，请联系客服。</p>

<h6>升级</h6>
<p>您可以在<a href="/price_table">价格页面</a>升级套餐来增加同时连接数。</p>""",
     # ── CONCURRENT EN ──
     """<h6>What is Simultaneous Access?</h6>
<p>The number of devices that can connect to VPN at the same time with one account.</p>

<h6>Connections by Plan</h6>
<ul>
<li>1 Line: 1 device</li>
<li>2 Line: 2 devices</li>
<li>6 Line: 6 devices (any device type)</li>
</ul>

<h6>When Exceeded</h6>
<p>If all allowed connections are in use, additional connections will be blocked. Disconnect another device first.</p>

<h6>Stale Sessions</h6>
<p>If a device disconnected abnormally, the session may remain active for 5-10 minutes before auto-cleanup. Contact support for immediate session reset.</p>

<h6>Upgrade</h6>
<p>You can increase your simultaneous connections by upgrading your plan on <a href="/price_table">the pricing page</a>.</p>"""),

    (7, 7,
     # ── LOGIN KO ──
     """<h6>비밀번호를 잊으셨을 때</h6>
<ul>
<li><a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a> 방문</li>
<li>[비밀번호 찾기] 클릭</li>
<li>이메일 입력 → 재설정 메일 발송</li>
<li>메일의 재설정 링크 클릭</li>
</ul>
<div class="notice">
※ 이메일이 오지 않으면 스팸/정크 폴더를 확인하세요.
</div>

<h6>이메일(ID)을 잊으셨을 때</h6>
<p>가입시 사용한 이메일이 ID입니다. 결제에 사용한 이메일을 확인하거나 고객센터에 문의하세요.</p>

<h6>로그인은 되지만 VPN이 연결 안될 때</h6>
<ul>
<li>구독 기간 만료 여부 확인 (마이페이지)</li>
<li>동시접속 초과 여부 확인</li>
<li>앱에 입력한 비밀번호 확인 (복사-붙여넣기 시 공백 포함 가능)</li>
</ul>

<h6>신규 가입</h6>
<p>👉 <a href="/regist">회원가입 하기</a></p>
<p>이메일과 비밀번호를 입력하여 가입합니다. 결제 후 즉시 이용 가능합니다.</p>""",
     # ── LOGIN ZH ──
     """<h6>忘记密码</h6>
<ul>
<li>访问 <a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a></li>
<li>点击[忘记密码]</li>
<li>输入邮箱 → 发送重置邮件</li>
<li>点击邮件中的重置链接</li>
</ul>
<div class="notice">
※ 如果没有收到邮件，请检查垃圾邮件文件夹。
</div>

<h6>忘记邮箱（ID）</h6>
<p>注册时使用的邮箱就是您的ID。请检查付款时使用的邮箱，或联系客服。</p>

<h6>可以登录但VPN无法连接</h6>
<ul>
<li>检查订阅是否过期（我的页面）</li>
<li>检查是否超出同时连接数</li>
<li>确认应用中输入的密码（复制粘贴时可能包含空格）</li>
</ul>

<h6>新用户注册</h6>
<p>👉 <a href="/regist">立即注册</a></p>
<p>输入邮箱和密码即可注册。付款后可立即使用服务。</p>""",
     # ── LOGIN EN ──
     """<h6>Forgot Password</h6>
<ul>
<li>Visit <a href="https://www.titanvpn.kr/login" target="_blank">titanvpn.kr/login</a></li>
<li>Click [Forgot Password]</li>
<li>Enter your email → Reset email will be sent</li>
<li>Click the reset link in the email</li>
</ul>
<div class="notice">
※ If you do not receive the email, check your spam/junk folder.
</div>

<h6>Forgot Email (ID)</h6>
<p>Your registration email is your ID. Check the email used for payment, or contact support.</p>

<h6>Logged In But VPN Not Connecting</h6>
<ul>
<li>Check if your subscription has expired (MyPage)</li>
<li>Check if simultaneous connections are exceeded</li>
<li>Verify the password entered in the app (spaces may be included when copy-pasting)</li>
</ul>

<h6>New Registration</h6>
<p>👉 <a href="/regist">Sign up here</a></p>
<p>Enter email and password to register. After payment, you can use the service immediately.</p>"""),
]

for cat_id, sort_order, ko, zh, en in items:
    c.execute(
        'INSERT INTO tbl_faq_item (category_id, sort_order, is_active, content_ko, content_zh, content_en) VALUES (%s,%s,1,%s,%s,%s)',
        [cat_id, sort_order, ko, zh, en]
    )
    print(f'Inserted item for category {cat_id}')

# Verify
c.execute('SELECT id, category_id, LEFT(content_ko, 40) FROM tbl_faq_item ORDER BY sort_order')
for r in c.fetchall():
    print(r)

print('\nDone! All FAQ data re-seeded.')
