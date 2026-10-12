# exporter.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from PIL import Image, ImageDraw, ImageFont


def export_tierlist_to_png(tierlist_data: Dict[str, Any], output_path: str) -> bool:
    """
    Renders the current tier list to a high-resolution PNG image ready for sharing.
    """
    try:
        title = tierlist_data.get("title", "LudusTier - Tier List de Jogos")
        tiers = tierlist_data.get("tiers", [])
        games = tierlist_data.get("games", [])

        # Filter out UNRANKED tier for clean export (only ranked tiers are exported)
        ranked_tiers = [t for t in tiers if t.get("id") != "UNRANKED"]
        if not ranked_tiers:
            return False

        # Group games by tier
        games_by_tier: Dict[str, List[Dict[str, Any]]] = {t["id"]: [] for t in ranked_tiers}
        for g in games:
            tid = g.get("tier")
            if tid in games_by_tier:
                games_by_tier[tid].append(g)

        card_w, card_h = 100, 150
        header_w = 110
        row_min_h = 150
        row_spacing = 8
        game_spacing = 6
        padding = 24
        header_title_h = 60

        # Calculate max games in any tier to determine canvas width
        max_games_in_row = max([len(lst) for lst in games_by_tier.values()] + [5])
        canvas_w = max(900, header_w + (max_games_in_row * (card_w + game_spacing)) + (padding * 2))

        # Calculate rows height
        total_h = padding + header_title_h
        row_heights = []
        for t in ranked_tiers:
            t_games = games_by_tier[t["id"]]
            # Number of rows needed if games wrap? For clean image export, single or multi-row:
            games_count = len(t_games)
            # Available width for games: canvas_w - (padding * 2) - header_w - 20
            avail_w = canvas_w - (padding * 2) - header_w - 20
            games_per_line = max(1, avail_w // (card_w + game_spacing))
            lines_needed = max(1, (games_count + games_per_line - 1) // games_per_line)
            rh = lines_needed * (card_h + game_spacing) + 12
            rh = max(rh, row_min_h)
            row_heights.append(rh)
            total_h += rh + row_spacing

        total_h += padding

        # Create canvas
        image = Image.new("RGB", (canvas_w, total_h), color="#16161a")
        draw = ImageDraw.Draw(image)

        # Draw Title
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 26)
            sub_font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 14)
            tier_font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 28)
        except Exception:
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 26)
                sub_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 14)
                tier_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 28)
            except Exception:
                title_font = ImageFont.load_default()
                sub_font = ImageFont.load_default()
                tier_font = ImageFont.load_default()

        draw.text((padding, padding), title, fill="#ffffff", font=title_font)
        draw.text((canvas_w - padding - 180, padding + 8), "Criado com LudusTier", fill="#7f849c", font=sub_font)

        # Draw Rows
        current_y = padding + header_title_h

        for idx, t in enumerate(ranked_tiers):
            tid = t["id"]
            rh = row_heights[idx]
            t_color = t.get("color", "#808080")
            t_name = t.get("name", tid)

            # Draw Row background
            row_rect = [
                (padding, current_y),
                (canvas_w - padding, current_y + rh),
            ]
            draw.rounded_rectangle(row_rect, radius=8, fill="#22232a", outline="#313244", width=1)

            # Draw Header Badge
            header_rect = [
                (padding, current_y),
                (padding + header_w, current_y + rh),
            ]
            draw.rounded_rectangle(header_rect, radius=8, fill=t_color)

            # Draw Tier Letter/Name inside badge
            # Center text in header
            bbox = draw.textbbox((0, 0), t_name, font=tier_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = padding + (header_w - tw) // 2
            ty = current_y + (rh - th) // 2
            text_color = t.get("text_color", "#000000")
            draw.text((tx, ty), t_name, fill=text_color, font=tier_font)

            # Draw Games
            t_games = games_by_tier[tid]
            avail_w = canvas_w - (padding * 2) - header_w - 20
            games_per_line = max(1, avail_w // (card_w + game_spacing))

            for g_idx, g in enumerate(t_games):
                line_idx = g_idx // games_per_line
                col_idx = g_idx % games_per_line

                gx = padding + header_w + 14 + (col_idx * (card_w + game_spacing))
                gy = current_y + 8 + (line_idx * (card_h + game_spacing))

                # Load Cover Image
                cover_p = (
                    g.get("cover_vertical")
                    or g.get("cover_path")
                    or g.get("cover_horizontal")
                    or g.get("cover_icon")
                )

                if cover_p and os.path.exists(cover_p):
                    try:
                        with Image.open(cover_p) as cimg:
                            cimg_rgb = cimg.convert("RGB")
                            resized = cimg_rgb.resize((card_w, card_h), Image.Resampling.LANCZOS)
                            image.paste(resized, (gx, gy))
                            # Border around card
                            draw.rectangle([(gx, gy), (gx + card_w, gy + card_h)], outline="#45475a", width=1)
                    except Exception as e:
                        print(f"[Export PNG] Error drawing cover for {g.get('title')}: {e}")
                        draw.rectangle([(gx, gy), (gx + card_w, gy + card_h)], fill="#313244", outline="#45475a")
                else:
                    draw.rectangle([(gx, gy), (gx + card_w, gy + card_h)], fill="#313244", outline="#45475a")

            current_y += rh + row_spacing

        # Save result
        image.save(output_path, "PNG", quality=95)
        return True
    except Exception as e:
        print(f"[Export PNG] Failed to export tier list image: {e}")
        return False


def export_tierlist_to_json(tierlist_data: Dict[str, Any], output_path: str) -> bool:
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tierlist_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Export JSON] Error: {e}")
        return False


def import_tierlist_from_json(input_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "games" in data:
                return data
    except Exception as e:
        print(f"[Import JSON] Error: {e}")
    return None
