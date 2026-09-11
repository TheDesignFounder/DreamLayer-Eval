import { useEffect, useState } from "react";

type BadgeResponse = {
  badge?: string;
};

const InferenceBadge = () => {
  const [badge, setBadge] = useState<string>("⏱ Loading...");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/internal/inference/badge", { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return res.json() as Promise<BadgeResponse>;
      })
      .then((data) => setBadge(data.badge ?? "N/A"))
      .catch((err) => {
        if (err.name === "AbortError") return;
        console.error("Badge fetch failed", err);
        setBadge("⚠️ Error");
      });

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <div className="rounded bg-gray-100 px-3 py-1 text-sm text-gray-600 shadow-sm ml-4">
      {badge}
    </div>
  );
};

export default InferenceBadge;
