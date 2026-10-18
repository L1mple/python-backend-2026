#!/usr/bin/env bash
BASE="${BASE:-http://localhost:8080}"
DURATION="${DURATION:-180}"     # по умолчанию 3 минуты
SLEEP_SEC="${SLEEP_SEC:-0.02}"  # пауза между итерациями (20 мс)

echo "==> Нагрузка на $BASE в течение ${DURATION}s (пауза ${SLEEP_SEC}s)"
echo "    Ctrl+C — остановить досрочно."
echo

# --- подготовка данных ---
ITEM_IDS=()
for i in $(seq 1 5); do
    id=$(curl -s -X POST "$BASE/item" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"Test $i\",\"price\":$((RANDOM % 100 + 10)).99}" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)
    [[ -n "$id" ]] && ITEM_IDS+=("$id")
done
echo "Создано товаров: ${#ITEM_IDS[@]}"

CART_IDS=()
for i in $(seq 1 3); do
    id=$(curl -s -X POST "$BASE/cart" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)
    [[ -n "$id" ]] && CART_IDS+=("$id")
done
echo "Создано корзин: ${#CART_IDS[@]}"
echo

# Проверяем, что сервис живой
if ! curl -s -o /dev/null "$BASE/item"; then
    echo "Ошибка: $BASE недоступен. Запущен ли docker compose up?"
    exit 1
fi

# --- основной цикл ---
end=$((SECONDS + DURATION))
i=0
start=$SECONDS

while [[ $SECONDS -lt $end ]]; do
    i=$((i + 1))

    case $((RANDOM % 10)) in
        0) curl -s -o /dev/null -X POST "$BASE/item" \
              -H "Content-Type: application/json" \
              -d "{\"name\":\"Load $i\",\"price\":$((RANDOM % 500 + 10)).0}" ;;
        1) curl -s -o /dev/null "$BASE/item" ;;
        2) if [[ ${#ITEM_IDS[@]} -gt 0 ]]; then
               id="${ITEM_IDS[$((RANDOM % ${#ITEM_IDS[@]}))]}"
               curl -s -o /dev/null "$BASE/item/$id"
           fi ;;
        3) if [[ ${#ITEM_IDS[@]} -gt 0 ]]; then
               id="${ITEM_IDS[$((RANDOM % ${#ITEM_IDS[@]}))]}"
               curl -s -o /dev/null -X PUT "$BASE/item/$id" \
                   -H "Content-Type: application/json" \
                   -d "{\"name\":\"Updated $i\",\"price\":$((RANDOM % 300)).0}"
           fi ;;
        4) if [[ ${#ITEM_IDS[@]} -gt 0 ]]; then
               id="${ITEM_IDS[$((RANDOM % ${#ITEM_IDS[@]}))]}"
               curl -s -o /dev/null -X PATCH "$BASE/item/$id" \
                   -H "Content-Type: application/json" \
                   -d "{\"price\":$((RANDOM % 100))}"
           fi ;;
        5) curl -s -o /dev/null -X POST "$BASE/cart" ;;
        6) curl -s -o /dev/null "$BASE/cart" ;;
        7) if [[ ${#CART_IDS[@]} -gt 0 ]]; then
               id="${CART_IDS[$((RANDOM % ${#CART_IDS[@]}))]}"
               curl -s -o /dev/null "$BASE/cart/$id"
           fi ;;
        8) if [[ ${#CART_IDS[@]} -gt 0 && ${#ITEM_IDS[@]} -gt 0 ]]; then
               cid="${CART_IDS[$((RANDOM % ${#CART_IDS[@]}))]}"
               iid="${ITEM_IDS[$((RANDOM % ${#ITEM_IDS[@]}))]}"
               curl -s -o /dev/null -X POST "$BASE/cart/$cid/add/$iid"
           fi ;;
        9) curl -s -o /dev/null "$BASE/item/999999" ;;
    esac

    sleep "$SLEEP_SEC"

    # Прогресс каждые 2 секунды
    if (( i % 50 == 0 )); then
        elapsed=$((SECONDS - start))
        printf "  прошло: %ss, итераций: %s\n" "$elapsed" "$i"
    fi
done

echo
echo "==> Готово. Итераций: $i, время: $((SECONDS - start))s"
echo "==> Grafana: http://localhost:3000"
