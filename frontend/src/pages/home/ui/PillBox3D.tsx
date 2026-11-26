import { useEffect, useRef } from "react";
import { createPillBoxScene, type PillBoxScene, type PillBoxState } from "./pillboxScene";

interface Props extends PillBoxState {
  onPress: () => void; // 약통을 누르면 (= 먹었어요)
  label: string; // 화면 읽기용 설명
}

// 3D 약통. 화면 읽기 기능은 3D를 읽지 못하므로 label과 아래 목록이 같은 정보를 줍니다.
export default function PillBox3D({ slotDone, current, rotate, onPress, label }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<PillBoxScene | null>(null);
  const slotCount = slotDone.length;

  useEffect(() => {
    if (!boxRef.current) return;
    const s = createPillBoxScene(boxRef.current, slotCount);
    sceneRef.current = s;
    return () => {
      s.dispose();
      sceneRef.current = null;
    };
  }, [slotCount]);

  useEffect(() => {
    sceneRef.current?.setState({ slotDone, current, rotate });
  }, [slotDone, current, rotate, slotCount]);

  useEffect(() => {
    sceneRef.current?.onPress(onPress);
  }, [onPress, slotCount]);

  return <div ref={boxRef} role="img" aria-label={label} className="w-full" />;
}
