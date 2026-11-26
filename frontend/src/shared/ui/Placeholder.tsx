// 아직 만들지 않은 화면 자리. 화면 번호는 와이어프레임 기준.
export default function Placeholder({ code, title }: { code: string; title: string }) {
  return (
    <div className="px-5 py-10 text-center">
      <p className="text-sm text-ink-sub">{code}</p>
      <h2 className="mt-1 text-xl font-bold">{title}</h2>
      <p className="mt-3 text-ink-sub">곧 만들 화면이에요.</p>
    </div>
  );
}
