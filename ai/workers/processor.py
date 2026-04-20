"""Обробник фонових завдань."""
import asyncio
import traceback
from typing import Optional

from .job_queue import job_queue
from backend.models.job import Job, JobStatus, ErrorCode
from ai.services import image_loader, segmentation, pose_detector, garment_prep, alignment, quality_control, diffusion, storage


async def process_job(job: Job) -> bool:
    """
    Обробляє одне завдання на примірку через весь конвеєр.
    
    Аргументи:
        job: Завдання для обробки
        
    Повертає:
        True якщо успішно, False якщо сталася помилка
    """
    try:
        print(f"Обробка завдання {job.job_id}...")
        
        # Оновлення статусу на 'processing' (обробляється)
        job.mark_processing()
        await job_queue.update_job(job)
        
        # КРОК 1 — ВАЛІДАЦІЯ ТА ЗАВАНТАЖЕННЯ
        print(f"  КРОК 1: Валідація та завантаження...")
        person_image, _ = await image_loader.load_and_normalize(
            image_url=job.user_image_url,
            image_path=job.user_image_path
        )
        garment_image, _ = await image_loader.load_and_normalize(
            image_url=job.product_image_url,
            image_path=job.product_image_path
        )
        
        # КРОК 2 — АНАЛІЗ ЛЮДИНИ
        print(f"  КРОК 2: Аналіз людини (Визначення пози)...")
        # Використовувати pose_hint якщо доступно (мокова перевірка). Резервний варіант - стандарт.
        person_keypoints = pose_detector.detect_pose(person_image, person_mask=None)
        
        # КРОК 3 — СЕГМЕНТАЦІЯ
        print(f"  КРОК 3: Сегментація...")
        masks = segmentation.segment_person(person_image, person_keypoints)
        person_mask = masks['person']
        torso_mask = masks['torso']
        arms_mask = masks['arms']
        
        # Повторне визначення пози з маскою людини в якості резерву, якщо спочатку знайдено погано
        if len(person_keypoints) < 4:
            person_keypoints = pose_detector.detect_pose(person_image, person_mask)
            # Re-segment with better keypoints to get accurate torso/arms masks
            masks = segmentation.segment_person(person_image, person_keypoints)
            person_mask = masks['person']
            torso_mask = masks['torso']
            arms_mask = masks['arms']
            
        # КРОК 4 — ОБРОБКА ОДЯГУ
        print(f"  КРОК 4: Обробка одягу...")
        garment_rgba, garment_mask, garment_anchors = garment_prep.prepare_garment(
            garment_image,
            garment_type=job.cloth_category
        )
        
        # КРОК 5 ТА 6 — ГЕОМЕТРИЧНЕ ВИРІВНЮВАННЯ ТА ОБРОБКА ПЕРЕКРИТТІВ
        print(f"  КРОК 5 ТА 6: Геометричне вирівнювання ({job.warp_mode.upper()}) та Обробка перекриттів...")
        head_mask = masks.get('head_neck')
        draft_composite, transformed_garment_mask, transform_params = alignment.align_and_composite(
            person_image=person_image,
            person_keypoints=person_keypoints,
            garment_image=garment_rgba,
            garment_mask=garment_mask,
            garment_anchors=garment_anchors,
            torso_mask=torso_mask,
            arms_mask=arms_mask,
            head_mask=head_mask,
            warp_mode=job.warp_mode
        )
        
        geometric_score, _ = quality_control.quality_control(
            garment_anchors=garment_anchors,
            person_keypoints=person_keypoints,
            garment_mask=transformed_garment_mask,
            person_mask=person_mask,
            transform_params=transform_params
        )
        
        # Створення структурованого звіту про якість для артефактів налагодження
        geo_quality_report = quality_control.build_quality_report(
            garment_anchors=garment_anchors,
            person_keypoints=person_keypoints,
            garment_mask=transformed_garment_mask,
            person_mask=person_mask,
            transform_params=transform_params
        )
        print(f"  Геометрична якість: {geo_quality_report.overall_score:.3f} "
              f"(успішно={geo_quality_report.passed}, реком_повтор={geo_quality_report.retry_recommended})")
        
        # КРОК 7 — КОМПОЗИТИНГ
        print(f"  КРОК 7: Композитинг чорнового зображення примірки...")
        coarse_tryon_image = draft_composite
        assert coarse_tryon_image is not None, "Для дифузії потрібен результат геометричного вирівнювання"
        final_result = coarse_tryon_image
        final_score = geometric_score
        
        if job.generation_mode == "fast":
            print(f"  Режим генерації 'fast' (швидкий). Дифузія пропускається...")
        else:
            # КРОК 8 ТА 9 — ДИФУЗІЙНЕ ПОКРАЩЕННЯ ТА ОЦІНКА ЯКОСТІ
            from ai.services.diffusion import RefinementMode
            refinement_mode = RefinementMode(job.refinement_mode)
            print(f"  КРОК 8: Дифузійне покращення ({refinement_mode.value}) та КРОК 9: Оцінка якості...")
            attempts = 0
            quality_passed = False
            
            while attempts <= job.max_retries and not quality_passed:
                attempts += 1
                try:
                    # Динамічне коригування рівня реалізму/сили при повторній спробі
                    current_realism = min(5, job.realism_level + (attempts - 1))
                    print(f"    Спроба {attempts}: Виклик локальної дифузії (realism={current_realism})...")
                    
                    candidate_result = await diffusion.refine_image_with_diffusion(
                        person_image=person_image,
                        garment_image=garment_image,
                        draft_composite=coarse_tryon_image,
                        preserve_face=job.preserve_face,
                        preserve_background=job.preserve_background,
                        realism_level=current_realism,
                        garment_type=job.cloth_category,
                        mode=refinement_mode,
                        garment_mask=transformed_garment_mask
                    )
                    
                    # Оцінка результату
                    score, passed = quality_control.evaluate_final_result(
                        original_image=person_image,
                        final_image=candidate_result,
                        person_mask=person_mask,
                        geometric_score=geometric_score
                    )
                    
                    print(f"    Оцінка перевірки якості: {score:.3f} (Пройдено: {passed})")
                    final_result = candidate_result
                    final_score = score
                    
                    if passed:
                        quality_passed = True
                    else:
                        print(f"    Перевірка якості не пройдена. Повторна спроба, якщо дозволяють ліміти...")
                        
                except diffusion.DiffusionAPIError as e:
                    print(f"    Спроба {attempts} невдала: {e.message}")
                    if attempts > job.max_retries:
                        print("    Досягнуто максимальної кількості спроб, повернення до чорнового композитингу.")
        
        # КРОК 10 — ЗБЕРЕЖЕННЯ
        print(f"  КРОК 10: Збереження фінального зображення у сховище...")
        result_url = storage.save_result(job.job_id, final_result)
        
        debug_artifacts = storage.save_debug_artifacts(
            job_id=job.job_id,
            person_mask=person_mask,
            torso_mask=torso_mask,
            garment_mask=transformed_garment_mask,
            draft_composite=coarse_tryon_image,
            keypoints=person_keypoints,
            quality_report=geo_quality_report.to_dict()
        )
        job.debug_artifacts = debug_artifacts
        
        # КРОК 11 — ВІДПОВІДЬ
        print(f"  КРОК 11: Завершення та статус відповіді...")
        job.mark_done(result_url, final_score)
        await job_queue.update_job(job)
        
        print(f"Завдання {job.job_id} успішно виконано!")
        return True
        
    except image_loader.ImageLoadError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except segmentation.SegmentationError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except pose_detector.PoseDetectionError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except garment_prep.GarmentPrepError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except alignment.AlignmentError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except quality_control.QualityCheckError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except storage.StorageError as e:
        job.mark_failed(e.error_code, e.message)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося помилкою: {e.message}")
        return False
        
    except Exception as e:
        # Перехоплення всіх непередбачуваних помилок
        error_msg = f"Непередбачувана помилка: {str(e)}\n{traceback.format_exc()}"
        job.mark_failed(ErrorCode.UNKNOWN_ERROR, error_msg)
        await job_queue.update_job(job)
        print(f"Завдання {job.job_id} завершилося із непередбачуваною помилкою: {error_msg}")
        return False


async def worker_loop():
    """
    Фоновий процес, що постійно обробляє завдання з черги.
    """
    print("Процес (worker) запущено, очікування завдань...")
    
    while True:
        try:
            # Отримати наступне завдання з черги
            job_id = await job_queue.get_next_job()
            
            if job_id is None:
                # Немає завдань, почекати
                await asyncio.sleep(0.1)
                continue
            
            # Отримати дані завдання
            job = await job_queue.get_job(job_id)
            
            if job is None:
                print(f"Увага: Завдання {job_id} не знайдено у сховищі")
                continue
            
            # Обробка завдання
            await process_job(job)
            
        except Exception as e:
            print(f"Помилка фонового процесу: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(1)


def start_worker():
    """Запускає фоновий процес (worker) у новій задачі."""
    asyncio.create_task(worker_loop())
