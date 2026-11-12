
class LayoutAnalyzer:

    def analyze(self, ocr_results):

        items = []

        for index, result in enumerate(ocr_results):

            if not result.bounding_box:
                continue

            box = result.bounding_box

            xs = [point[0] for point in box]
            ys = [point[1] for point in box]

            items.append({
                "detection_id": index,
                "text": result.text,
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
                "center_y": (min(ys) + max(ys)) / 2,
                "height": max(ys) - min(ys)
            })

        items.sort(key=lambda item: (item["center_y"], item["x_min"]))

        lines = []

        for item in items:

            matching_line = None

            for line in lines:

                threshold = max(
                    8,
                    0.5 * max(item["height"], line["height"])
                )

                if abs(item["center_y"] - line["center_y"]) <= threshold:
                    matching_line = line
                    break

            if matching_line is None:

                lines.append({
                    "detection_ids": [item["detection_id"]],
                    "texts": [item["text"]],
                    "center_y": item["center_y"],
                    "height": item["height"]
                })

            else:

                matching_line["detection_ids"].append(item["detection_id"])
                matching_line["texts"].append(item["text"])

                matching_line["center_y"] = sum(
                    element["center_y"]
                    for element in items
                    if element["detection_id"] in matching_line["detection_ids"]
                ) / len(matching_line["detection_ids"])

                matching_line["height"] = max(
                    matching_line["height"],
                    item["height"]
                )

        output = []

        for line in lines:

            # Keep detections in left-to-right order.
            ordered_ids = sorted(
                line["detection_ids"],
                key=lambda detection_id: next(
                    item["x_min"]
                    for item in items
                    if item["detection_id"] == detection_id
                )
            )

            output.append({
                "text": " ".join(
                    next(
                        item["text"]
                        for item in items
                        if item["detection_id"] == detection_id
                    )
                    for detection_id in ordered_ids
                ),
                "detection_ids": ordered_ids
            })

        return output
