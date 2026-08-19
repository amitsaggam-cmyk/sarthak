import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { fetchAuthedFile } from "../api";

function isImageFile(filename) {
  return /\.(png|jpe?g|gif|bmp|webp)$/i.test(filename || "");
}

export default function DocumentThumbnail({ url, filename }) {
  const [previewUrl, setPreviewUrl] = useState(null);

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;

    if (isImageFile(filename)) {
      fetchAuthedFile(url)
        .then((result) => {
          if (cancelled) {
            URL.revokeObjectURL(result.url);
            return;
          }
          objectUrl = result.url;
          setPreviewUrl(result.url);
        })
        .catch(() => {});
    }

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, filename]);

  if (previewUrl) {
    return <img alt={filename} src={previewUrl} />;
  }
  return (
    <span className="docThumbFallback">
      <FileText size={22} />
    </span>
  );
}