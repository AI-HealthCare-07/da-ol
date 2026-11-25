// A-1-2 추가 정보 입력 + 약관 동의 (POST /users/me/profile). 다음 작업에서 폼을 채웁니다.
export default function ProfileSetupPage() {
  return (
    <div className="mx-auto max-w-[480px] px-6 py-12">
      <p className="text-sm text-ink-sub">A-1-2</p>
      <h1 className="mt-1 text-2xl font-bold">추가 정보 입력</h1>
      <p className="mt-3 text-ink-sub">이름, 생년월일, 성별과 필수 약관 동의를 받는 화면이에요.</p>
    </div>
  );
}
