import type { VideoCategory } from "@/lib/types";

export type VideoCategoryOption = {
  value: VideoCategory;
  label: string;
  description: string;
};

export const VIDEO_CATEGORY_OPTIONS: VideoCategoryOption[] = [
  {
    value: "lifestyle",
    label: "Lifestyle",
    description: "Day-in-the-life, routines, and personal storytelling formats."
  }
];
