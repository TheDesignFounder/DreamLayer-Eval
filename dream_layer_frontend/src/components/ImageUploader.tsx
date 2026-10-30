import React from 'react';
import SingleImageUploader from './SingleImageUploader';
import DualImageUploader from './DualImageUploader';
import { useImg2ImgGalleryStore } from '@/stores/useImg2ImgGalleryStore';

interface ImageUploaderProps {
  activeImg2ImgTool?: string;
}

const ImageUploader = ({ activeImg2ImgTool = "img2img" }: ImageUploaderProps) => {
  const { inputImage, setInputImage } = useImg2ImgGalleryStore();

  const handleImageChange = (file: File) => {
    const url = URL.createObjectURL(file);
    setInputImage({ url, file });
  };

  const handleMaskChange = (file: File) => {
    // For now, we'll just handle the main image
    // TODO: Add mask handling in the future
    console.log("Mask change:", file);
  };

  const handleImageDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleImageChange(file);
    }
  };

  const handleMaskDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleMaskChange(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const getButtonLabel = () => {
    switch (activeImg2ImgTool) {
      case "img2img":
        return "Send to inpaint";
      case "inpaint":
        return "Send to img2img";
      default:
        return "Send to img2img";
    }
  };

  const shouldShowButton = () => {
    return activeImg2ImgTool !== "inpaint-upload";
  };

  const handleClearImage = () => {
    if (inputImage?.url) {
      URL.revokeObjectURL(inputImage.url);
    }
    setInputImage(null);
  };

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-bold text-primary">0. Upload Image</h4>
        
      </div>
      {activeImg2ImgTool === "inpaint-upload" ? (
        <DualImageUploader
          imagePreview={inputImage?.url || null}
          maskPreview={null}
          onImageChange={handleImageChange}
          onMaskChange={handleMaskChange}
          onImageClear={handleClearImage}
          onMaskClear={() => {}}
          onImageDrop={handleImageDrop}
          onMaskDrop={handleMaskDrop}
          onDragOver={handleDragOver}
        />
      ) : (
        <SingleImageUploader
          onDrop={handleImageDrop}
          onDragOver={handleDragOver}
        />
      )}
    </div>
  );
};

export default ImageUploader;
